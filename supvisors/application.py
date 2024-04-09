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

import ast
import re
from typing import Any, Dict, List, Optional, Sequence, Union

from supervisor.loggers import Logger
from supervisor.states import ProcessStates, RUNNING_STATES

from .process import ProcessStatus
from .ttypes import (ApplicationStates, DistributionRules, NameList, NameSet, Payload, StartingStrategies,
                     StartingFailureStrategies, RunningFailureStrategies, ApplicationStatusParseError)
from .utils import WILDCARD

# additional annotation types
ProcessList = List[ProcessStatus]
ProcessMap = Dict[str, ProcessStatus]  # {process_name: ProcessStatus}


class ApplicationRules:
    """ Definition of the rules for starting an application, iaw rules file.

    Attributes are:
        - managed: set to True when application rules are found from the rules file ;
        - distribution: the distribution rule of the application ;
        - identifiers: the Supervisors where the application can be started if not distributed (default: all) ;
        - hash_identifiers: when # rule is used, the application can be started on one of the Supervisors identified ;
        - start_sequence: defines the order of this application when starting all the applications
          in the DEPLOYMENT state (0 means: no automatic start) ;
        - stop_sequence: defines the order of this application when stopping all the applications
          (0 means: immediate stop) ;
        - starting_strategy: defines the strategy to apply when choosing the identifier where the process
          shall be started during the starting of the application ;
        - starting_failure_strategy: defines the strategy to apply when a required process cannot be started
          during the starting of the application ;
        - running_failure_strategy: defines the default strategy to apply when a required process crashes
          when the application is running ;
        - status_formula: the formula describing the application operational status ;
        - status_tree: the AST-parsed formula describing the application operational status.
    """

    # attributes
    managed: bool = False
    distribution: DistributionRules = DistributionRules.ALL_INSTANCES
    start_sequence: int = 0
    stop_sequence: int = -1
    starting_strategy: StartingStrategies = StartingStrategies.CONFIG
    starting_failure_strategy: StartingFailureStrategies = StartingFailureStrategies.ABORT
    running_failure_strategy: RunningFailureStrategies = RunningFailureStrategies.CONTINUE
    _status_formula: Optional[str] = None
    _status_tree: Optional[ast.Module] = None

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # attributes with mutable default values
        self.identifiers: NameList = [WILDCARD]
        self.at_identifiers: NameList = []
        self.hash_identifiers: NameList = []

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    @property
    def status_formula(self) -> str:
        """ Return the status formula if it has passed the AST parsing. """
        return self._status_formula

    @status_formula.setter
    def status_formula(self, formula: str):
        """ AST-parse the status formula. """
        # AST-parse the formula
        try:
            tree = ast.parse(formula)
        except SyntaxError:
            raise ApplicationStatusParseError('AST parse failure')
        # there must be only one element in the body
        if len(tree.body) != 1:
            raise ApplicationStatusParseError('unsupported AST expression')
        # store the expression
        self._status_formula = formula
        self._status_tree = tree

    @property
    def status_tree(self) -> Optional[ast.Expr]:
        """ Return the root expression of the AST-parsed status formula. """
        return self._status_tree.body[0].value if self._status_tree else None

    def check_stop_sequence(self, application_name: str) -> None:
        """ Check the stop_sequence value.
        If stop_sequence hasn't been set from the rules file, use the same value as start_sequence.

        :param application_name: the name of the application considered.
        :return: None
        """
        if self.stop_sequence < 0:
            self.logger.trace(f'ApplicationRules.check_stop_sequence: {application_name}'
                              f' - set stop_sequence to {self.start_sequence} ')
            self.stop_sequence = self.start_sequence

    def check_hash_identifiers(self, application_name: str) -> None:
        """ When a '#' is set in application rules, an association has to be done between the 'index' of the application
        and the index of the Supervisor in the applicable identifier list.
        Unlike programs, there is no unquestionable index that Supvisors could get because Supervisor does not support
        homogeneous applications. It thus has to be a convention.
        The chosen convention is that the application_name MUST match r'[-_]\\d+$'. The first index name is 1.

        hash_identifiers is expected to contain:
            - either ['*'] when all Supervisors are applicable
            - or any subset of these Supervisors.

        :param application_name: the name of the application considered.
        :return: None
        """
        error = True
        result = re.match(r'.*[-_](\d+)$', application_name)
        if not result:
            self.logger.error(f'ApplicationRules.check_hash_identifiers: {application_name} incompatible'
                              ' with the use of #')
        else:
            application_number = int(result.group(1)) - 1
            if application_number < 0:
                self.logger.error(f'ApplicationRules.check_hash_identifiers: index of {application_name} must be > 0')
            else:
                self.logger.trace(f'ApplicationRules.check_hash_identifiers: application_name={application_name}'
                                  f' application_number={application_number}')
                if '*' in self.hash_identifiers:
                    # all identifiers defined in the supvisors section of the supervisor configuration are applicable
                    ref_identifiers = list(self.supvisors.mapper.instances.keys())
                else:
                    # the subset of applicable identifiers is the hash_identifiers
                    ref_identifiers = self.hash_identifiers
                # if there are more application instances than possible identifiers, roll over
                index = application_number % len(ref_identifiers)
                self.identifiers = [ref_identifiers[index]]
                self.logger.debug(f'ApplicationRules.check_hash_identifiers: application_name={application_name}'
                                  f' identifiers={self.identifiers}')
                error = False
        if error:
            self.logger.debug(f'ApplicationRules.check_hash_identifiers: {application_name} start_sequence reset')
            self.start_sequence = 0

    def check_dependencies(self, application_name: str) -> None:
        """ Update rules after they have been read from the rules file.

        :param application_name: the name of the application considered.
        :return: None
        """
        self.check_stop_sequence(application_name)
        if self.hash_identifiers:
            self.check_hash_identifiers(application_name)

    def __str__(self) -> str:
        """ Get the application rules as string.

        :return: the printable application rules
        """
        return (f'managed={self.managed} distribution={self.distribution.name} identifiers={self.identifiers}'
                f' start_sequence={self.start_sequence} stop_sequence={self.stop_sequence}'
                f' starting_strategy={self.starting_strategy.name}'
                f' starting_failure_strategy={self.starting_failure_strategy.name}'
                f' running_failure_strategy={self.running_failure_strategy.name}'
                f' status_formula={self.status_formula}')

    # serialization
    def serial(self) -> Payload:
        """ Get a serializable form of the application rules.
        No information for unmanaged applications.

        :return: the application rules in a dictionary
        """
        if self.managed:
            payload = {'managed': True, 'distribution': self.distribution.name,
                       'identifiers': self.identifiers,
                       'start_sequence': self.start_sequence, 'stop_sequence': self.stop_sequence,
                       'starting_strategy': self.starting_strategy.name,
                       'starting_failure_strategy': self.starting_failure_strategy.name,
                       'running_failure_strategy': self.running_failure_strategy.name,
                       'status_formula': self.status_formula or ''}
            return payload
        return {'managed': False}


class HomogeneousGroup:
    """ Class used to store all the application processes that are configured using the same program definition.
    It has been introduced to manage the # rules optionally set to some processes of the application start sequence
    to distribute the processes over a set of Supvisors instances. """

    # information part
    program_name: str = ''
    # applicable process at/hash rules
    at_identifiers: Optional[NameList] = None
    hash_identifiers: Optional[NameList] = None

    def __init__(self, program_name: str, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param program_name: the name of the homogeneous group
        :param supvisors: the global Supvisors structure
        """
        self.supvisors = supvisors
        self.program_name = program_name
        # the list of processes belonging to the group
        self.processes: ProcessList = []

    @property
    def logger(self) -> Logger:
        """ Return the Supvisors logger. """
        return self.supvisors.logger

    def add_process(self, process: ProcessStatus) -> None:
        """ Add a process to the homogeneous group.
        process is expected to have the correct program_name (not checked here).

        :param process: the process belonging to the group
        :return: None
        """
        self.processes.append(process)
        # check at/hash rule consistence
        # NOTE: Based on the same program definition, is it possible to give multiple rules driven by patterns
        #       e.g. from program:prg with numprocs=30, patterns prg_0* / prog_1* / prg_2*
        if process.rules.at_identifiers:
            if self.at_identifiers is not None and self.at_identifiers != process.rules.at_identifiers:
                self.logger.error('HomogeneousGroup.add_process: inconsistent identifiers rules applied on'
                                  f' homogeneous group={self.program_name} - @={self.at_identifiers} vs '
                                  f' @={process.rules.at_identifiers}')
            self.at_identifiers = process.rules.at_identifiers
        if process.rules.hash_identifiers:
            if self.hash_identifiers is not None and self.hash_identifiers != process.rules.hash_identifiers:
                self.logger.error('HomogeneousGroup.add_process: inconsistent identifiers rules applied on'
                                  f' homogeneous group={self.program_name} - #={self.hash_identifiers} vs '
                                  f' #={process.rules.hash_identifiers}')
            self.hash_identifiers = process.rules.hash_identifiers
        if self.at_identifiers and self.hash_identifiers:
            self.logger.error('HomogeneousGroup.add_process: inconsistent identifiers rules applied on'
                              f' homogeneous group={self.program_name} - @={self.at_identifiers} and '
                              f' #={self.hash_identifiers}')
            self.hash_identifiers = None

    def remove_process(self, process: ProcessStatus) -> None:
        """ Remove a process from the homogeneous group.

        :param process: the process to remove from the group
        :return: None
        """
        self.processes.remove(process)

    def resolve_rules(self) -> None:
        """ When a '#' or a '@' is set in program rules, an association has to be made between the process_index
        of the process and the index of the Supvisors identifier in the applicable identifiers list.
        In this case, rules.hash_identifiers or rules.hash_identifiers is expected to contain:
            - either ['*'] when all Supervisors are applicable
            - or any subset of these Supervisors.

        The hash_identifiers were originally solved just after the Process rules were loaded because all Supvisors
        instances were known right from the start.

        The discovery mode changes things a bit. In this case, Supvisors instances are not known in advance.
        However, the list can only increase in time and the ordering is kept, even when considering auto-fencing.

        That's why the resolution logic can be kept quite identical as before. It just needs to be deferred,
        and eventually updated.

        NOTE: At resolution time, some of these processes may have already been started on the 'wrong' Supvisors
              instance using direct calls to Supervisor, or by setting their autostart option to True.
              The resolution logic in Supvisors does NOT consider this case because it is clearly a misuse.

        Updating the process rules has no effect on a running process. The update will effectively take place when the
        process will be started again.

        :return: None
        """
        if self.at_identifiers:
            self.assign_at_identifiers()
        if self.hash_identifiers:
            self.assign_hash_identifiers()

    def assign_at_identifiers(self) -> None:
        """ Assign identifiers wrt the '@' rule set on the homogeneous group.
        The assignment is strictly limited by the length of the identifiers list, without roll-over.
        If the number of candidate processes is greater than the candidate identifiers, the processes in excess
        cannot be started using Supvisors.

        :return: None
        """
        # get process list ordered by process_index
        process_list = sorted(self.processes, key=lambda x: x.process_index)
        # get unassigned processes
        unassigned_processes = [process for process in process_list
                                if process.rules.at_identifiers]
        if unassigned_processes:
            # get instances
            if WILDCARD in self.at_identifiers:
                # all identifiers defined in the supvisors section of the supervisor configuration file are applicable
                ref_identifiers = list(self.supvisors.mapper.instances.keys())
            else:
                # the subset of applicable identifiers is the second element of rule 'identifiers'
                # filter the unknown identifiers (or remaining aliases)
                ref_identifiers = self.supvisors.mapper.filter(self.at_identifiers)
            self.logger.debug(f'ProcessRules.assign_at_identifiers: program={self.program_name}'
                              f' ref_identifiers={ref_identifiers}')
            # the aim of at_identifiers is to distribute the processes over a list of Supvisors instances,
            #   without having 2 processes assigned to the same identifier
            # get assigned identifiers, assuming rules identifiers have size == 1
            assigned_identifiers = [process.rules.identifiers[0] for process in process_list
                                    if process.rules.identifiers]
            self.logger.debug(f'ProcessRules.assign_at_identifiers: program={self.program_name}'
                              f' assigned_identifiers={assigned_identifiers}')
            # deduce unassigned identifiers
            unassigned_identifiers = [identifier for identifier in ref_identifiers
                                      if identifier not in assigned_identifiers]
            self.logger.debug(f'ProcessRules.assign_at_identifiers: program={self.program_name}'
                              f' unassigned_identifiers={unassigned_identifiers}')
            # resolve what can be done
            for process, identifier in zip(unassigned_processes, unassigned_identifiers):
                process.rules.at_identifiers = []
                process.rules.identifiers = [identifier]
                self.logger.info(f'ProcessRules.assign_at_identifiers: namespec={process.namespec} assigned to'
                                 f' identifiers={process.rules.identifiers}')
            # WARN: even if not in discovery mode, do NOT remove the 'at' status from homogeneous group
            #       the assignment is final but the number of processes in a homogeneous group can change
            #       (through the update_numprocs XML-RPC)

    def assign_hash_identifiers(self) -> None:
        """ Assign identifiers wrt the '#' rule set on the homogeneous group.
        The assignment is NOT limited by the length of the identifiers list.
        If the number of candidate processes is greater than the candidate `identifiers`, the assignment is performed
        by rolling over the identifiers list.

        :return: None
        """
        # get process list ordered by process_index
        process_list = sorted(self.processes, key=lambda x: x.process_index)
        # get unassigned processes
        unassigned_processes = [process for process in process_list
                                if process.rules.hash_identifiers]
        if unassigned_processes:
            # get instances
            if WILDCARD in self.hash_identifiers:
                # all identifiers defined in the supvisors section of the supervisor configuration file are applicable
                ref_identifiers = list(self.supvisors.mapper.instances.keys())
            else:
                # the subset of applicable identifiers is the second element of rule 'identifiers'
                # filter the unknown identifiers (or remaining aliases)
                ref_identifiers = self.supvisors.mapper.filter(self.hash_identifiers)
            self.logger.debug(f'ProcessRules.assign_hash_identifiers: program={self.program_name}'
                              f' ref_identifiers={ref_identifiers}')
            # the aim of hash_identifiers is to distribute the processes over a list of Supvisors instances, so
            # unassigned processes will go to the least loaded Supvisors instance, wrt the homogeneous group considered
            process_count_per_instance = {identifier: [] for identifier in ref_identifiers}
            for process in process_list:
                if process.rules.identifiers:
                    # NOTE: assumed size == 1 and identifier in ref_identifiers
                    process_count_per_instance[process.rules.identifiers[0]].append(process)
            # re-arrange to keep ref_identifiers ordering
            process_count = [[len(process_count_per_instance[identifier]), identifier]
                             for identifier in ref_identifiers]
            self.logger.debug(f'ProcessRules.assign_hash_identifiers: program={self.program_name}'
                              f' process_count={process_count}')
            for process in unassigned_processes:
                # choose the Supvisors instance the least loaded (without sorting by identifier name)
                count, identifier = identifier_count = min(process_count, key=lambda x: x[0])
                process.rules.hash_identifiers = []
                process.rules.identifiers = [identifier]
                self.logger.info(f'ProcessRules.assign_hash_identifiers: namespec={process.namespec} assigned to'
                                 f' identifiers={process.rules.identifiers}')
                # increment identifier counter
                identifier_count[0] = count + 1
            # WARN: even if not in discovery mode, do NOT remove the 'at' status from homogeneous group
            #       the assignment is final but the number of processes in a homogeneous group can change
            #       (through the update_numprocs XML-RPC)


class ApplicationStatus:
    """ Class defining the status of an application in Supvisors.

    Attributes are:
        - application_name: the name of the application, corresponding to the Supervisor group name,
        - state: the state of the application in ApplicationStates,
        - major_failure: a status telling if a required process is stopped while the application is running,
        - minor_failure: a status telling if an optional process has crashed while the application is running,
        - processes: the map (key is process name) of the ProcessStatus belonging to the application,
        - process_groups: the ProcessStatus map, sorted as homogeneous groups,
        - rules: the ApplicationRules applicable to this application,
        - start_sequence: the sequencing to start the processes belonging to the application, as a dictionary.
        - stop_sequence: the sequencing to stop the processes belonging to the application, as a dictionary.

    For start and stop sequences, each entry is a list of processes having the same sequence order, used as key.
    """

    # types for annotations
    ApplicationSequence = Dict[int, ProcessList]
    PrintableApplicationSequence = Dict[int, Sequence[str]]
    HomogeneousGroupsMap = Dict[str, HomogeneousGroup]  # {program_name: HomogeneousGroup}

    # information part
    application_name: str = ''
    _state: ApplicationStates = ApplicationStates.STOPPED
    major_failure: bool = False
    minor_failure: bool = False
    # process part
    rules: Optional[ApplicationRules] = None

    def __init__(self, application_name: str, rules: ApplicationRules, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param application_name: the name of the application
        :param rules: the rules applicable to the application
        :param supvisors: the global Supvisors structure
        """
        self.supvisors = supvisors
        self.application_name = application_name
        self.rules = rules
        # attributes with mutable default values
        self.processes: ProcessMap = {}
        self.process_groups: ApplicationStatus.HomogeneousGroupsMap = {}
        self.start_sequence: ApplicationStatus.ApplicationSequence = {}
        self.stop_sequence: ApplicationStatus.ApplicationSequence = {}

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    # status methods
    def running(self) -> bool:
        """ Return True if the application is running.

        :return: the running status of the application
        """
        return self.state in [ApplicationStates.STARTING, ApplicationStates.RUNNING]

    def stopped(self) -> bool:
        """ Return True if the application is stopped.

        :return: the stopped status of the application
        """
        return self.state == ApplicationStates.STOPPED

    def never_started(self) -> bool:
        """ Return True if the application has never been started.

        :return: True if the processes of the application have never been started
        """
        return all(info['state'] == ProcessStates.STOPPED and info['stop'] == 0
                   for proc in self.processes.values()
                   for info in proc.info_map.values())

    @property
    def state(self) -> ApplicationStates:
        """ Getter of state attribute.

         :return: the application state
         """
        return self._state

    @state.setter
    def state(self, new_state: ApplicationStates) -> None:
        """ Setter of state attribute.

        :param new_state: the new application state
        :return: None
        """
        if self._state != new_state:
            self._state = new_state
            self.logger.info(f'Application.state: {self.application_name} is {self.state.name}')

    def has_running_processes(self) -> bool:
        """ Check if one of the application processes is running.
        The application state may be STOPPED in this case if the running process is out of the starting sequence.

        :return: True if any of the application processes is running
        """
        return any(process.running() for process in self.processes.values())

    def get_operational_status(self) -> str:
        """ Get a description of the operational status of the application.

        :return: the operational status as string
        """
        if self.state == ApplicationStates.RUNNING:
            if self.major_failure:
                return 'Not Operational'
            if self.minor_failure:
                return 'Degraded'
            return 'Operational'
        return ''

    # serialization
    def serial(self) -> Payload:
        """ Get a serializable form of the application status.

        :return: the application status in a dictionary
        """
        return {'application_name': self.application_name, 'managed': self.rules.managed,
                'statecode': self.state.value, 'statename': self.state.name,
                'major_failure': self.major_failure, 'minor_failure': self.minor_failure}

    def __str__(self) -> str:
        """ Get the application status as string.

        :return: the printable application status
        """
        return (f'application_name={self.application_name} managed={self.rules.managed} state={self.state.name}'
                f' major_failure={self.major_failure} minor_failure={self.minor_failure}')

    # process methods
    def add_process(self, process: ProcessStatus) -> None:
        """ Add a new process to the process list.

        :param process: the process status to be added to the application
        :return: None
        """
        self.logger.trace(f'ApplicationStatus.add_process: {self.application_name}'
                          f' - adding process={process.process_name}')
        self.processes[process.process_name] = process
        # add to homogeneous groups
        group = self.process_groups.get(process.program_name)
        if not group:
            group = HomogeneousGroup(process.program_name, self.supvisors)
            self.process_groups[process.program_name] = group
        group.add_process(process)

    def remove_process(self, process_name: str) -> None:
        """ Remove a process from the process list.

        :param process_name: the process to be removed from the application
        :return: None
        """
        self.logger.trace(f'ApplicationStatus.remove_process: {self.application_name}'
                          f' - removing process={process_name}')
        process = self.processes.pop(process_name)
        # clear entry from homogeneous groups
        self.process_groups[process.program_name].remove_process(process)
        if not self.process_groups[process.program_name].processes:
            del self.process_groups[process.program_name]
        # re-evaluate sequences and status
        self.update_sequences()
        self.update()

    def resolve_rules(self):
        """ Call for hash identifiers resolution as the application is marked to be started in the Supvisors Starter.
        The resolution will be based on the current known list of Supvisors instances.
        """
        # get the programs involved in the starting sequence
        sequenced_programs = {process.program_name
                              for sub_seq in self.start_sequence.values()
                              for process in sub_seq}
        # set their rules identifiers
        for program_name in sequenced_programs:
            self.process_groups[program_name].resolve_rules()

    def possible_identifiers(self) -> NameList:
        """ Return the list of Supervisor identifiers where the application could be started, assuming that its
        processes cannot be distributed over multiple Supvisors instances.
        To achieve that, three conditions:
            - the Supervisor shall know all the application programs (real-time configuration) ;
            - the Supervisor identifier shall be allowed (explicitly or implicitly) in the rules file ;
            - the programs shall not be disabled.

        :return: the list of identifiers where the program could be started.
        """
        rules_identifiers = self.rules.identifiers
        if '*' in self.rules.identifiers:
            filtered_identifiers = list(self.supvisors.mapper.instances.keys())
        else:
            # filter the unknown identifiers (due to Supvisors discovery mode, any identifier may be lately known)
            filtered_identifiers = self.supvisors.mapper.filter(rules_identifiers)
        # get the identifiers of all application processes
        actual_identifiers: List[NameSet] = [{identifier
                                              for identifier, info in process.info_map.items()
                                              if not info['disabled']}
                                             for process in self.processes.values()]
        if actual_identifiers:
            # the common list is the intersection of all subsets
            actual_identifiers = actual_identifiers[0].intersection(*actual_identifiers)
        self.logger.debug(f'ApplicationStatus.possible_identifiers: application_name={self.application_name}'
                          f' actual_identifiers={actual_identifiers}')
        # intersect with rules
        return [identifier
                for identifier in filtered_identifiers
                if identifier in actual_identifiers]

    def possible_node_identifiers(self) -> NameList:
        """ Same principle as possible_identifiers, excepted that the possibilities are built from the nodes
        rather than from the strict identifiers.

        Note: Some elements in the returned list of identifiers may not fit to the possibilities got from the
              intermediate actual_identifiers, that is based on the real-time configurations.

        :return: the list of identifiers where the program could be started.
        """
        rules_identifiers = self.rules.identifiers
        if '*' in self.rules.identifiers:
            filtered_identifiers = list(self.supvisors.mapper.instances.keys())
        else:
            # filter the unknown identifiers (due to Supvisors discovery mode, any identifier may be lately known)
            filtered_identifiers = self.supvisors.mapper.filter(rules_identifiers)
        # get the identifiers of all application processes
        actual_identifiers: List[NameSet] = [{identifier
                                              for identifier, info in process.info_map.items()
                                              if not info['disabled']}
                                             for process in self.processes.values()]
        self.logger.trace(f'ApplicationStatus.possible_node_identifiers: application_name={self.application_name}'
                          f' actual_identifiers={actual_identifiers}')
        # test nodes individually
        all_node_identifiers = set()
        for node, identifiers_list in self.supvisors.mapper.nodes.items():
            # from all node identifiers, intersect with rules identifiers
            filtered_node_identifiers = {x for x in identifiers_list if x in filtered_identifiers}
            self.logger.trace(f'ApplicationStatus.possible_node_identifiers: application_name={self.application_name}'
                              f' node={node} filtered_node_identifiers={filtered_node_identifiers}')
            # check that every process has a solution on the node
            config_identifiers = set()
            for process_identifiers in actual_identifiers:
                process_node_identifiers = filtered_node_identifiers & set(process_identifiers)
                if not process_node_identifiers:
                    self.logger.debug('ApplicationStatus.possible_node_identifiers:'
                                      f' application_name={self.application_name} has no solution on node={node}')
                    break
                # add remaining identifiers to the intersections union
                config_identifiers.update(process_node_identifiers)
            else:
                self.logger.debug('ApplicationStatus.possible_node_identifiers:'
                                  f' application_name={self.application_name} node={node}'
                                  f' solution={config_identifiers}')
                # add the node solution to the application solutions
                all_node_identifiers.update(config_identifiers)
        self.logger.debug(f'ApplicationStatus.possible_node_identifiers: application_name={self.application_name}'
                          f' all_node_identifiers={all_node_identifiers}')
        # return the node identifiers keeping the ordering defined in rules
        return [identifier
                for identifier in filtered_identifiers
                if identifier in all_node_identifiers]

    def get_instance_processes(self, identifier: str) -> ProcessList:
        """ Return the list of application processes configured in the Supervisor instance.

        :param identifier: the Supervisor instance where the processes qre configured
        :return: the list of application processes in the Supervisor instance
        """
        return [process for process in self.processes.values()
                if identifier in process.info_map]

    # sequencing methods
    @staticmethod
    def printable_sequence(application_sequence: ApplicationSequence) -> PrintableApplicationSequence:
        """ Get printable application sequence for log traces.
        Only the name of the process is kept.

        :return: the simplified sequence
        """
        return {seq: [proc.process_name for proc in proc_list]
                for seq, proc_list in application_sequence.items()}

    def update_sequences(self) -> None:
        """ Evaluate the sequencing of the starting / stopping application from its list of processes.
        This makes sense only for managed applications.

        :return: None
        """
        self.start_sequence.clear()
        self.stop_sequence.clear()
        # consider only managed applications for start sequence
        if self.rules.managed:
            # fill ordering iaw process rules
            for process in self.processes.values():
                self.start_sequence.setdefault(process.rules.start_sequence, []).append(process)
            self.logger.debug(f'ApplicationStatus.update_sequences: application_name={self.application_name}'
                              f' start_sequence={self.printable_sequence(self.start_sequence)}')
        else:
            self.logger.info(f'ApplicationStatus.update_sequences: application_name={self.application_name}'
                             ' is not managed so start sequence is undefined')
        # stop sequence is applicable to all applications
        for process in self.processes.values():
            # fill ordering iaw process rules
            self.stop_sequence.setdefault(process.rules.stop_sequence, []).append(process)
        self.logger.debug(f'ApplicationStatus.update_sequences: application_name={self.application_name}'
                          f' stop_sequence={self.printable_sequence(self.stop_sequence)}')

    def get_start_sequenced_processes(self) -> ProcessList:
        """ Return the processes included in the application start sequence.
        The sequence 0 is removed as it corresponds to processes that are not meant to be auto-started.

        :return: the processes included in the application start sequence.
        """
        return [process for seq, sub_seq in self.start_sequence.items()
                for process in sub_seq if seq > 0]

    def get_start_sequence_expected_load(self) -> int:
        """ Return the sum of the expected loading of the processes in the starting sequence.
        This is used only in the event where the application is not distributed and the whole application loading
        has to be checked on a single Supervisor.

        :return: the expected loading of the application.
        """
        return sum(process.rules.expected_load for process in self.get_start_sequenced_processes())

    # global status methods
    def update(self) -> None:
        """ Update the state and the operational status of the application.

        :return: None
        """
        # get the processes from the starting sequence
        sequenced_processes: ProcessMap = {process.process_name: process
                                           for sub_seq in self.start_sequence.values()
                                           for process in sub_seq}
        # update the application state
        self.state = self.update_state()
        # reset failures
        self.major_failure, self.minor_failure = False, False
        # update the application operational status
        if self.rules.status_tree:
            self.update_status_formula(sequenced_processes)
        else:
            self.update_status_required(sequenced_processes)
        self.logger.debug(f'ApplicationStatus.update: application_name={self.application_name}'
                          f' major_failure={self.major_failure} minor_failure={self.minor_failure}')

    def update_state(self) -> ApplicationStates:
        """ Update the state of the application iaw the state of its processes.
        This is a displayed status, and thus relies on the displayed process state, considering the forced state.

        :return: None
        """
        starting, running, stopping = False, False, False
        # evaluate the application state from the state of its processes
        for process in self.processes.values():
            self.logger.trace(f'ApplicationStatus.update_state: application_name={self.application_name}'
                              f' process={process.namespec} displayed_state={process.displayed_state}')
            if process.displayed_state == ProcessStates.RUNNING:
                running = True
            elif process.displayed_state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                starting = True
            elif process.displayed_state == ProcessStates.STOPPING:
                stopping = True
        self.logger.trace(f'ApplicationStatus.update_state: application_name={self.application_name}'
                          f' - starting={starting} running={running} stopping={stopping}')
        # apply rules for state
        if stopping:
            # if at least one process is STOPPING, let's consider that application is stopping
            # here priority is given to STOPPING over STARTING
            return ApplicationStates.STOPPING
        if starting:
            # if at least one process is STARTING, let's consider that application is starting
            return ApplicationStates.STARTING
        if running:
            # all processes in the sequence are RUNNING, so application is RUNNING
            return ApplicationStates.RUNNING
        # all processes in the sequence are STOPPED, so application is STOPPED
        return ApplicationStates.STOPPED

    def update_status_required(self, sequenced_processes: ProcessMap) -> None:
        """ Update the operational status of the application iaw its processes' state.
        Any required process in failure implies a major failure.
        Any non-required process in failure implies a minor failure if part of the starting sequence.

        NOTE: This is the legacy method to evaluate the application status.
              The formula method is now preferred.

        :return: None
        """
        possible_major_failure = False
        for process in self.processes.values():
            self.logger.trace(f'ApplicationStatus.update_status_required: application_name={self.application_name}'
                              f' process={process.namespec} state={process.displayed_state_string()}'
                              f' required={process.rules.required} exit_expected={process.expected_exit}')
            if (process.displayed_state in [ProcessStates.FATAL, ProcessStates.UNKNOWN]
                    or (process.displayed_state == ProcessStates.EXITED and not process.expected_exit)):
                # a major/minor failure is raised in these states depending on the required option
                if process.rules.required:
                    self.major_failure = True
                elif process.process_name in sequenced_processes:
                    self.minor_failure = True
            elif process.displayed_state == ProcessStates.STOPPED:
                # possible major failure raised if process STOPPED
                # consideration will depend on the global application state
                if process.rules.required:
                    possible_major_failure = True
        self.logger.trace(f'ApplicationStatus.update_status_required: application_name={self.application_name}'
                          f' major_failure={self.major_failure} minor_failure={self.minor_failure}'
                          f' possible_major_failure={possible_major_failure}')
        # possible major failure is confirmed if the application is not stopped
        if self.state != ApplicationStates.STOPPED:
            self.major_failure |= possible_major_failure
        # reset the minor failure if the major failure is set
        if self.major_failure:
            self.minor_failure = False

    def evaluate(self, node: ast.Expr) -> Union[bool, List[bool]]:
        """ Resolution of the AST expression.

        All tree nodes are expected to be:
            * a boolean operator (or, and) ;
            * a unary operator (not) ;
            * a function (any, all).

        All tree leaves are expected to be string corresponding to:
            * a process name ;
            * a pattern matching at least one process name.

        When multiple process names are found from a pattern, it is expected that a function evaluates them.

        :param node: The current AST node.
        :return: Either a boolean value or a list a boolean values intended to be used by an upper Call.
        """
        # handle string leaves (ast.Str is deprecated from Python < 3.8)
        leaf: Optional[str] = None
        if type(node) is ast.Str:
            leaf = node.s
        elif type(node) is ast.Constant and type(node.value) is str:
            leaf = node.value
        if leaf is not None:
            if leaf in self.processes:
                return self._get_process_status(leaf)
            matches = self._get_matches(leaf)
            if len(matches) == 1:
                return self._get_process_status(matches[0])
            elif len(matches) >= 1:
                return [self._get_process_status(x) for x in matches]
            raise ApplicationStatusParseError(f'no match for expression={node.s}')
        # handle any/all functions
        if type(node) is ast.Call:
            if node.func.id not in ['all', 'any']:
                raise ApplicationStatusParseError(f'unsupported function={node.func.id}')
            args_eval = self.evaluate(node.args[0])
            if type(args_eval) is bool:
                args_eval = [args_eval]
            return eval(f'{node.func.id}({args_eval})')
        # handle and/or operators
        if type(node) is ast.BoolOp:
            args_eval = [self.evaluate(x) for x in node.values]
            if any(type(x) is not bool for x in args_eval):
                raise ApplicationStatusParseError(f'cannot apply BoolOp on unresolved expression')
            if type(node.op) is ast.And:
                return all(args_eval)
            if type(node.op) is ast.Or:
                return any(args_eval)
        # handle not operator
        if type(node) is ast.UnaryOp:
            if type(node.op) is ast.Not:
                args_eval = self.evaluate(node.operand)
                if type(args_eval) is not bool:
                    raise ApplicationStatusParseError(f'cannot apply UnaryOp on unresolved expression')
                return not args_eval
            raise ApplicationStatusParseError(f'unsupported UnaryOp={type(node.op).__name__}')
        raise ApplicationStatusParseError(f'unsupported Expr={type(node).__name__}')

    def update_status_formula(self, sequenced_processes: ProcessMap) -> None:
        """ Update the operational status of the application iaw its processes' state.
        The major failure is set according to the status formula.
        If no major failure, any process in failure implies a minor failure if part of the starting sequence.

        :return: None
        """
        # evaluate the status formula against the current processes' state
        try:
            result = self.evaluate(self.rules.status_tree)
            if type(result) is not bool:
                raise ApplicationStatusParseError('status formula cannot be resolved')
        except ApplicationStatusParseError as exc:
            self.logger.error(f'ApplicationStatus.update_status_formula: application_name={self.application_name}'
                              f' - {exc}')
            self.major_failure = True
        else:
            self.major_failure = not result
        # check for a minor failure in start sequence processes
        if not self.major_failure:
            for process in sequenced_processes.values():
                self.logger.trace(f'ApplicationStatus.update_status_formula: application_name={self.application_name}'
                                  f' process={process.namespec} state={process.displayed_state_string()}'
                                  f' exit_expected={process.expected_exit}')
                if (process.displayed_state in [ProcessStates.FATAL, ProcessStates.UNKNOWN]
                        or (process.displayed_state == ProcessStates.EXITED and not process.expected_exit)):
                    self.minor_failure = True

    def _get_process_status(self, process_name: str) -> bool:
        """ Return False if the process is in a stopped (displayed) state.
        Exception is made for EXITED expected, which is considered as normal. """
        process = self.processes[process_name]
        return ((process.displayed_state in RUNNING_STATES)
                or (process.displayed_state == ProcessStates.EXITED and process.expected_exit))

    def _get_matches(self, pattern_name: str) -> List[str]:
        """ Return the process names matching the pattern. """
        results = []
        pattern = re.compile(r'^%s$' % pattern_name)
        for name in self.processes.keys():
            if pattern.match(name):
                results.append(name)
        return results
