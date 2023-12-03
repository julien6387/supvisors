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

from typing import Any, Dict, List, Optional, Set, Tuple

from supvisors.internal_com.mapper import SupvisorsMapper
from .application import ApplicationStatus
from .process import ProcessStatus
from .ttypes import NameList, NameSet, LoadMap, ConciliationStrategies, StartingStrategies, RunningFailureStrategies

# annotation types
LoadDetails = Tuple[LoadMap, LoadMap, LoadMap]


class AbstractStrategy(object):
    """ Base class for a common constructor. """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors instance
        """
        self.supvisors = supvisors
        self.logger = supvisors.logger


# Strategy management for Starting
class AbstractStartingStrategy(AbstractStrategy):
    """ Base class for a starting strategy. """

    # Annotation types
    LoadingValidity = Tuple[bool, int, int]
    LoadingValidityMap = Dict[str, LoadingValidity]
    IdentifierLoadMap = List[Tuple[str, int, int]]

    def is_loading_valid(self, identifier: str, expected_load: int, load_details: LoadDetails) -> LoadingValidity:
        """ Check if the node hosting the Supvisors instance can support the additional load.

        :param identifier: the identifier of the Supvisors instance
        :param expected_load: the load to add to the Supvisors instance
        :param load_details: the load details per identifier and node
        :return: a tuple with a boolean telling if the additional load is possible on the node hosting the Supvisors
        instance, the current load on the node and the current load on the Supvisors instance
        """
        # load_request_map: the unconsidered load per identifier
        # node_load_map: the current load per node
        # node_load_request_map: the unconsidered load per node
        load_request_map, node_load_map, node_load_request_map = load_details
        self.logger.trace(f'AbstractStartingStrategy.is_loading_valid: identifier={identifier}'
                          f' expected_load={expected_load} load_request_map={load_request_map}'
                          f' node_load_map={node_load_map} node_load_request_map={node_load_request_map}')
        status = self.supvisors.context.instances[identifier]
        self.logger.trace(f'AbstractStartingStrategy.is_loading_valid: Supvisors={identifier}'
                          f' state={status.state.name}')
        # calculate the theoretical load on the node
        ip_address = status.supvisors_id.ip_address
        node_loading = node_load_map.get(ip_address, 0) + node_load_request_map.get(ip_address, 0)
        # check if the node and the Supvisors instance can support the
        instance_loading = status.get_load() + load_request_map.get(identifier, 0)
        self.logger.debug(f'AbstractStartingStrategy.is_loading_valid: Supvisors={identifier}'
                          f' instance_loading={instance_loading} expected_load={expected_load}')
        return node_loading + expected_load <= 100, node_loading, instance_loading

    def get_loading_and_validity(self, identifiers: NameList, expected_load: int,
                                 load_details: LoadDetails) -> LoadingValidityMap:
        """ Return the report of loading capability of all iSupvisors instances iaw the additional load required.

        :param identifiers: the identifiers of the Supvisors instances considered
        :param expected_load: the additional load to consider for the program to be started
        :param load_details: the load details per identifier and node
        :return: the list of identifiers corresponding to the Supvisors instances that can support the additional load
        """
        loading_validity_map = {identifier: self.is_loading_valid(identifier, expected_load, load_details)
                                for identifier in identifiers}
        self.logger.trace(f'AbstractStartingStrategy.get_loading_and_validity:'
                          f' loading_validity_map={loading_validity_map}')
        return loading_validity_map

    def sort_valid_by_instance_load(self, loading_validity_map: LoadingValidityMap) -> IdentifierLoadMap:
        """ Sort the loading report by instance load and considering only valid identifiers.
        If multiple instances have an equivalent load, the node load is considered.

        :param loading_validity_map: the loading report
        :return: the valid identifiers sorted by instance load
        """
        result = sorted([(identifier, node_load, instance_load)
                         for identifier, (validity, node_load, instance_load) in loading_validity_map.items()
                         if validity], key=lambda x: (x[2], x[1]))
        self.logger.trace(f'AbstractStartingStrategy.sort_valid_by_instance_load: result={result}')
        return result

    def sort_valid_by_node_load(self, loading_validity_map: LoadingValidityMap) -> IdentifierLoadMap:
        """ Sort the loading report by node load and considering only valid identifiers.
        If multiple nodes have an equivalent load, the instance load is considered.

        :param loading_validity_map: the loading report
        :return: the valid identifiers sorted by node load
        """
        result = sorted([(identifier, node_load, instance_load)
                         for identifier, (validity, node_load, instance_load) in loading_validity_map.items()
                         if validity], key=lambda x: (x[1], x[2]))
        self.logger.trace(f'AbstractStartingStrategy.sort_valid_by_node_load: result={result}')
        return result

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the Supvisors instance that can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in SupvisorsInstanceStatus.

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the chosen identifier
        """
        raise NotImplementedError


class ConfigStrategy(AbstractStartingStrategy):
    """ Strategy designed to choose the Supvisors instance using the order defined in the configuration file. """

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the first Supvisors instance in the list that can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in SupvisorsInstanceStatus.

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the chosen identifier
        """
        self.logger.debug(f'ConfigStrategy.get_supvisors_instance: identifiers={identifiers}'
                          f' expected_load={expected_load} load_details={load_details}')
        loading_validity_map = self.get_loading_and_validity(identifiers, expected_load, load_details)
        # the first valid element is the right one
        return next((identifier for identifier, (validity, _, _) in loading_validity_map.items() if validity), None)


class LessLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to share the loading among all the Supvisors instances. """

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the Supvisors instance having the lowest load provided that its node can support the additional load
        requested.

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the chosen identifier
        """
        self.logger.trace(f'LessLoadedStrategy.get_supvisors_instance: identifiers={identifiers}'
                          f' expected_load={expected_load} load_details={load_details}')
        loading_validity_map = self.get_loading_and_validity(identifiers, expected_load, load_details)
        sorted_identifiers = self.sort_valid_by_instance_load(loading_validity_map)
        return sorted_identifiers[0][0] if sorted_identifiers else None


class LessLoadedNodeStrategy(AbstractStartingStrategy):
    """ Strategy designed to share the loading among all nodes supporting the Supvisors instances. """

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the Supvisors instance whose node has the lowest load that can support the additional load requested.

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the chosen identifier
        """
        self.logger.trace(f'LessLoadedNodeStrategy.get_supvisors_instance: identifiers={identifiers}'
                          f' expected_load={expected_load} load_details={load_details}')
        loading_validity_map = self.get_loading_and_validity(identifiers, expected_load, load_details)
        sorted_identifiers = self.sort_valid_by_node_load(loading_validity_map)
        return sorted_identifiers[0][0] if sorted_identifiers else None


class MostLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to maximize the loading of a Supvisors instance. """

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the Supvisors instance having the highest load provided that its node can support the additional load
        requested

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the chosen identifier
        """
        self.logger.trace(f'MostLoadedStrategy.get_supvisors_instance: identifiers={identifiers}'
                          f' expected_load={expected_load} load_details={load_details}')
        loading_validity_map = self.get_loading_and_validity(identifiers, expected_load, load_details)
        sorted_identifiers = self.sort_valid_by_instance_load(loading_validity_map)
        return sorted_identifiers[-1][0] if sorted_identifiers else None


class MostLoadedNodeStrategy(AbstractStartingStrategy):
    """ Strategy designed to maximize the loading of a node hosting Supvisors instances. """

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the Supvisors instance whose node has the highest load that can support the additional load
        requested.

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the list of identifiers corresponding to the Supvisors instances that can support the additional load
        """
        self.logger.trace(f'MostLoadedNodeStrategy.get_supvisors_instance: identifiers={identifiers}'
                          f' expected_load={expected_load} load_details={load_details}')
        loading_validity_map = self.get_loading_and_validity(identifiers, expected_load, load_details)
        sorted_identifiers = self.sort_valid_by_node_load(loading_validity_map)
        return sorted_identifiers[-1][0] if sorted_identifiers else None


class LocalStrategy(AbstractStartingStrategy):
    """ Strategy designed to start the process on the local Supvisors instance. """

    def get_supvisors_instance(self, identifiers: NameList, expected_load: int,
                               load_details: LoadDetails) -> Optional[str]:
        """ Choose the local Supvisors instance provided that it can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in SupvisorsInstanceStatus.

        :param identifiers: the identifiers of the candidate Supvisors instances
        :param expected_load: the load of the program to be started
        :param load_details: the load details per identifier and node
        :return: the list of identifiers corresponding to the Supvisors instances that can support the additional load
        """
        local_identifier = self.supvisors.mapper.local_identifier
        self.logger.trace(f'LocalStrategy.get_supvisors_instance: identifiers={identifiers}'
                          f' local_identifier={local_identifier} expected_load={expected_load}'
                          f' load_details={load_details}')
        if local_identifier not in identifiers:
            # the local Supvisors instance is not among the candidates
            return None
        loading_validity_map = self.get_loading_and_validity(identifiers, expected_load, load_details)
        validity, _, _ = loading_validity_map[local_identifier]
        return local_identifier if validity else None


def get_node_load_request_map(mapper: SupvisorsMapper, load_request_map: LoadMap):
    """ Sum the load_request_map per identifier by node.

    :param mapper: the Supvisors instances mapper
    :param load_request_map: the unconsidered loads per identifier
    :return: the request load per node
    """
    node_load_request_map = {node_name: 0 for node_name in mapper.nodes}
    for identifier, load in load_request_map.items():
        ip_address = mapper.instances[identifier].ip_address
        node_load_request_map[ip_address] += load
    return node_load_request_map


def create_strategy(supvisors: Any, strategy: StartingStrategies) -> AbstractStartingStrategy:
    """ Factory for starting strategies.

    :param supvisors: the global Supvisors structure
    :param strategy: the strategy used to choose a Supvisors instance
    :return:
    """
    if strategy == StartingStrategies.CONFIG:
        return ConfigStrategy(supvisors)
    if strategy == StartingStrategies.LESS_LOADED:
        return LessLoadedStrategy(supvisors)
    if strategy == StartingStrategies.MOST_LOADED:
        return MostLoadedStrategy(supvisors)
    if strategy == StartingStrategies.LOCAL:
        return LocalStrategy(supvisors)
    if strategy == StartingStrategies.LESS_LOADED_NODE:
        return LessLoadedNodeStrategy(supvisors)
    if strategy == StartingStrategies.MOST_LOADED_NODE:
        return MostLoadedNodeStrategy(supvisors)


def get_supvisors_instance(supvisors: Any, strategy: StartingStrategies, identifiers: NameList,
                           expected_load: int) -> Optional[str]:
    """ Creates a strategy and let it find a Supvisors instance to start a process having a defined load.

    :param supvisors: the global Supvisors structure
    :param strategy: the strategy used to choose a Supvisors instance
    :param identifiers: the identifiers of the candidate Supvisors instances (from configuration perspective)
    :param expected_load: the load of the program to be started
    :return: the identifier of the Supvisors instance that can support the additional load
    """
    # restrict the candidate Supvisors instances to those that are actually running
    running_identifiers = supvisors.context.running_identifiers()
    candidate_identifiers = [identifier for identifier in identifiers if identifier in running_identifiers]
    if not candidate_identifiers:
        return None
    # create the relevant strategy to choose a Supvisors instance among the candidates
    instance = create_strategy(supvisors, strategy)
    # consider all pending starting requests into global load
    load_request_map = supvisors.starter.get_load_requests()
    supvisors.logger.debug(f'get_supvisors_instance: load_request_map={load_request_map}')
    node_load_request_map = get_node_load_request_map(supvisors.mapper, load_request_map)
    supvisors.logger.debug(f'get_supvisors_instance: node_load_request_map={node_load_request_map}')
    # get nodes load
    node_load_map = supvisors.context.get_nodes_load()
    supvisors.logger.debug(f'get_supvisors_instance: node_load_map={node_load_map}')
    # apply strategy
    return instance.get_supvisors_instance(candidate_identifiers, expected_load,
                                           (load_request_map, node_load_request_map, node_load_map))


def get_node(supvisors: Any, strategy: StartingStrategies, identifiers: NameList, expected_load: int) -> Optional[str]:
    """ Creates a strategy and let it find the node to start a process having a defined load.

    :param supvisors: the global Supvisors structure
    :param strategy: the strategy used to choose a Supvisors instance
    :param identifiers: the identifiers of the candidate Supvisors instances (from configuration perspective)
    :param expected_load: the load of the program to be started
    :return: the IP address of the node that can support the additional load
    """
    # Note: the node load is the sum of the load of its instances
    # the selection of an instance is conditioned to the fact that the node can support the additional load
    # if the node can support, there must be one of its instance that can support
    identifier = get_supvisors_instance(supvisors, strategy, identifiers, expected_load)
    # get the corresponding IP address
    if identifier:
        return supvisors.mapper.instances[identifier].ip_address


# Strategy management for Conciliation
class SenicideStrategy(AbstractStrategy):
    """ Strategy designed to stop the oldest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the most recently and stopping the others """
        for process in conflicts:
            # determine the process with lower uptime (the youngest)
            # uptime is used as there is guarantee that the Supvisors instances are time synchronized
            # so comparing start dates may be irrelevant
            saved_identifier = min(process.running_identifiers, key=lambda x: process.info_map[x]['uptime'])
            self.logger.warn(f'SenicideStrategy.conciliate: keep {process.namespec} at {saved_identifier}')
            # stop other processes. work on copy as it may change during iteration
            # Stopper can't be used here as it would stop all processes
            running_identifiers = process.running_identifiers.copy()
            running_identifiers.remove(saved_identifier)
            self.logger.debug(f'SenicideStrategy.conciliate: stop {process.namespec} on {running_identifiers}')
            self.supvisors.stopper.stop_process(process, running_identifiers, False)
        # trigger all Stopper jobs at once
        self.supvisors.stopper.next()


class InfanticideStrategy(AbstractStrategy):
    """ Strategy designed to stop the youngest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the least recently and stopping the others """
        for process in conflicts:
            # determine the process with higher uptime (the oldest)
            saved_identifier = max(process.running_identifiers, key=lambda x: process.info_map[x]['uptime'])
            self.logger.warn(f'InfanticideStrategy.conciliate: keep {process.namespec} at {saved_identifier}')
            # stop other processes. work on copy as it may change during iteration
            # Stopper can't be used here as it would stop all processes
            running_identifiers = process.running_identifiers.copy()
            running_identifiers.remove(saved_identifier)
            self.logger.debug(f'InfanticideStrategy.conciliate: stop {process.namespec} on {running_identifiers}')
            self.supvisors.stopper.stop_process(process, running_identifiers, False)
        # trigger all Stopper jobs at once
        self.supvisors.stopper.next()


class UserStrategy(AbstractStrategy):
    """ Strategy designed to let the user do the job. """

    def conciliate(self, conflicts):
        """ Does nothing. """
        pass


class StopStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by stopping all processes. """
        for process in conflicts:
            self.logger.warn(f'StopStrategy.conciliate: {process.namespec} on {process.running_identifiers}')
            self.supvisors.stopper.stop_process(process, trigger=False)
        # trigger all at once
        self.supvisors.stopper.next()


class RestartStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes and to restart a single instance. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by notifying the Stopper to restart the process. """
        for process in conflicts:
            self.logger.warn(f'RestartStrategy.conciliate: {process.namespec}')
            self.supvisors.stopper.default_restart_process(process, False)
        # trigger the stopper jobs at once
        self.supvisors.stopper.next()


class FailureStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes and to apply the running failure strategy
    related to the process. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by notifying the failure handler to apply the running failure strategy
        related to the process. """
        # stop all processes and add them to the failure handler
        for process in conflicts:
            self.supvisors.stopper.stop_process(process, trigger=False)
            self.logger.warn(f'FailureStrategy.conciliate: {process.namespec}')
            self.supvisors.failure_handler.add_default_job(process)
        self.supvisors.stopper.next()
        # trigger the jobs of the failure handler directly (could wait for next tick)
        self.supvisors.failure_handler.trigger_jobs()


def conciliate_conflicts(supvisors, strategy, conflicts):
    """ Creates a strategy and let it conciliate the conflicts. """
    instance = None
    if strategy == ConciliationStrategies.SENICIDE:
        instance = SenicideStrategy(supvisors)
    elif strategy == ConciliationStrategies.INFANTICIDE:
        instance = InfanticideStrategy(supvisors)
    elif strategy == ConciliationStrategies.USER:
        instance = UserStrategy(supvisors)
    elif strategy == ConciliationStrategies.STOP:
        instance = StopStrategy(supvisors)
    elif strategy == ConciliationStrategies.RESTART:
        instance = RestartStrategy(supvisors)
    elif strategy == ConciliationStrategies.RUNNING_FAILURE:
        instance = FailureStrategy(supvisors)
    # apply strategy to conflicts
    if instance:
        instance.conciliate(conflicts)


# Strategy management for a Running Failure
class RunningFailureHandler(AbstractStrategy):
    """ Handler of running failures.
    The strategies are linked to the RunningFailureStrategies enumeration.

    Any Supvisors instance may hold application processes with different running failure strategies.
    If the Supvisors instance becomes inactive, as seen from another Supvisors instance, it could lead
    to have all possible strategies to apply on the same application and related processes, which makes no sense.

    So it has been chosen to give a priority to the strategies.
    The highest priority is for the most restricting strategy, consisting in stopping the application.
    Then, the priority goes to the strategy having the highest impact, i.e. restarting the application.
    The lowest priority is for the most simple strategy consisting in restarting only the involved process.

    Attributes are:

        - stop_application_jobs: the set of application names to be stopped ;
        - restart_application_jobs: the set of application names to be restarted ;
        - restart_process_jobs: the set of processes to be restarted ;
        - continue_process_jobs: the set of processes to be ignored (only for log).
    """

    def __init__(self, supvisors):
        AbstractStrategy.__init__(self, supvisors)
        # the initial jobs
        self.stop_application_jobs: Set[ApplicationStatus] = set()
        self.restart_application_jobs: Set[ApplicationStatus] = set()
        self.restart_process_jobs: Set[ProcessStatus] = set()
        self.continue_process_jobs: Set[ProcessStatus] = set()

    def abort(self):
        """ Clear all sets. """
        self.stop_application_jobs = set()
        self.restart_application_jobs = set()
        self.restart_process_jobs = set()
        self.continue_process_jobs = set()

    def add_stop_application_job(self, application: ApplicationStatus) -> None:
        """ Add the application name to the stop_application_jobs, checking if this job supersedes other jobs.

        :param application: the application to stop due to a failed process
        :return: None
        """
        self.logger.info(f'RunningFailureHandler.add_stop_application_job: adding {application.application_name}')
        self.stop_application_jobs.add(application)
        # stop_application_jobs take precedence over all other jobs related to this application
        self.restart_application_jobs.discard(application)
        for job_set in [self.restart_process_jobs, self.continue_process_jobs]:
            for process in list(job_set):
                if process.application_name == application.application_name:
                    job_set.discard(process)

    def add_restart_application_job(self, application: ApplicationStatus) -> None:
        """ Add the application name to the restart_application_jobs, checking if this job supersedes other jobs
        and assuming that stop_application_jobs takes precedence over restart_application_jobs.

        :param application: the application to restart due to a failed process
        :return: None
        """
        if application in self.stop_application_jobs:
            self.logger.info(f'RunningFailureHandler.add_restart_application_job: {application.application_name}'
                             ' not added because already in stop_application_jobs')
            return
        self.logger.info(f'RunningFailureHandler.add_restart_application_job: adding {application.application_name}')
        self.restart_application_jobs.add(application)
        # restart_application_jobs take precedence over all process jobs
        # remove only processes that are declared in the application start sequence
        sequenced_processes = application.get_start_sequenced_processes()
        for job_set in [self.restart_process_jobs, self.continue_process_jobs]:
            for process in list(job_set):
                if process.application_name == application.application_name and process in sequenced_processes:
                    job_set.remove(process)

    def add_restart_process_job(self, application: ApplicationStatus, process: ProcessStatus) -> None:
        """ Add the process to the restart_process_jobs, checking if this job supersedes other jobs and assuming that:
            * stop_application_jobs takes precedence over restart_process_jobs ;
            * restart_application_jobs takes precedence over restart_process_jobs if the process is in the application
              starting sequence.

        :param application: the application including the failed process to restart
        :param process: the failed process to restart
        :return: None
        """
        if application in self.stop_application_jobs:
            self.logger.info(f'RunningFailureHandler.add_restart_process_job: {process.namespec} not added'
                             f' because {process.application_name} already in stop_application_jobs')
            return
        if application in self.restart_application_jobs:
            if process in application.get_start_sequenced_processes():
                self.logger.info(f'RunningFailureHandler.add_restart_process_job: {process.namespec} not added'
                                 f' because {process.application_name} already in restart_application_jobs')
                return
        self.logger.info(f'RunningFailureHandler.add_restart_process_job: adding {process.namespec}')
        self.restart_process_jobs.add(process)
        # restart_process_jobs take precedence over continue_process_jobs
        self.continue_process_jobs.discard(process)

    def add_continue_process_job(self, application: ApplicationStatus, process: ProcessStatus) -> None:
        """ Add the application name to the continue_process_jobs, checking if this job supersedes other jobs
        and assuming that all other jobs takes precedence over continue_process_jobs.

        :param application: the application including the failed process
        :param process: the failed process
        :return: None
        """
        if application in self.stop_application_jobs:
            self.logger.info(f'RunningFailureHandler.add_continue_process_job: {process.namespec} not added'
                             f' because {process.application_name} already in stop_application_jobs')
            return
        if application in self.restart_application_jobs:
            if process in application.get_start_sequenced_processes():
                self.logger.info(f'RunningFailureHandler.add_continue_process_job: {process.namespec} not added'
                                 f' because {process.application_name} already in restart_application_jobs')
                return
        if process in self.restart_process_jobs:
            self.logger.info(f'RunningFailureHandler.add_continue_process_job: {process.namespec} not added'
                             ' because already in restart_process_jobs')
            return
        self.logger.info(f'RunningFailureHandler.add_continue_process_job: adding {process.namespec}')
        self.continue_process_jobs.add(process)

    def add_job(self, strategy, process):
        """ Add a process or the related application name in the relevant set,
        iaw the strategy set in parameter and the priorities defined above. """
        self.logger.trace(f'RunningFailureHandler.add_job: START stop_application_jobs={self.stop_application_jobs}'
                          f' restart_application_jobs={self.restart_application_jobs}'
                          f' restart_process_jobs={self.restart_process_jobs}'
                          f' continue_process_jobs={self.continue_process_jobs}')
        application = self.supvisors.context.applications[process.application_name]
        # new job may supersede others of may be superseded by existing ones
        if strategy == RunningFailureStrategies.STOP_APPLICATION:
            self.add_stop_application_job(application)
        elif strategy == RunningFailureStrategies.RESTART_APPLICATION:
            self.add_restart_application_job(application)
        elif strategy == RunningFailureStrategies.RESTART_PROCESS:
            self.add_restart_process_job(application, process)
        elif strategy == RunningFailureStrategies.CONTINUE:
            self.add_continue_process_job(application, process)
        self.logger.trace(f'RunningFailureHandler.add_job: END stop_application_jobs={self.stop_application_jobs}'
                          f' restart_application_jobs={self.restart_application_jobs}'
                          f' restart_process_jobs={self.restart_process_jobs}'
                          f' continue_process_jobs={self.continue_process_jobs}')

    def add_default_job(self, process: ProcessStatus):
        """ Add a process or the related application name in the relevant set,
        iaw the strategy set in process rules and the priorities defined above. """
        self.add_job(process.rules.running_failure_strategy, process)
        # check strategy promotion
        if process.rules.running_failure_strategy == RunningFailureStrategies.RESTART_PROCESS:
            # this is the case where the Supvisors instance has been invalidated
            # if the application is stopped due to such failure, it is likely that the full application needs a restart
            # rather than uncorrelated process restarts
            application = self.supvisors.context.applications[process.application_name]
            if application.stopped() and process in application.get_start_sequenced_processes():
                # promote to RESTART_APPLICATION if process is in application start_sequence
                # the job that has just been added will be swiped out as this strategy takes precedence
                self.logger.warn(f'RunningFailureHandler.add_default_job: program={process.namespec}'
                                 ' with strategy=RESTART_PROCESS in an application stopped will use a promoted'
                                 ' strategy=RESTART_APPLICATION')
                self.add_job(RunningFailureStrategies.RESTART_APPLICATION, process)

    def get_application_job_names(self) -> NameSet:
        """ Get all application names involved in Commanders.

        :return: the list of application names
        """
        return self.supvisors.starter.get_application_job_names() | self.supvisors.stopper.get_application_job_names()

    def trigger_stop_application_jobs(self, job_applications: NameSet) -> None:
        """ Trigger the STOP_APPLICATION strategy on stored jobs. """
        for application in list(self.stop_application_jobs):
            if application.application_name in job_applications:
                self.logger.debug('RunningFailureHandler.trigger_stop_application_jobs: defer'
                                  f' {application.application_name} stop')
            else:
                self.logger.info('RunningFailureHandler.trigger_stop_application_jobs: stopping'
                                 f' {application.application_name}')
                self.stop_application_jobs.remove(application)
                self.supvisors.stopper.stop_application(application, False)

    def trigger_restart_application_jobs(self, job_applications: NameSet) -> None:
        """ Trigger the RESTART_APPLICATION strategy on stored jobs.
        Stop application if necessary and defer start until application is fully stopped. """
        for application in list(self.restart_application_jobs):
            if application.application_name in job_applications:
                self.logger.debug(f'RunningFailureHandler.trigger_restart_application_jobs: defer'
                                  ' {application.application_name} restart')
            else:
                self.logger.info('RunningFailureHandler.trigger_restart_application_jobs: restarting'
                                 f' {application.application_name}')
                self.restart_application_jobs.remove(application)
                # first stop the application
                self.supvisors.stopper.default_restart_application(application, False)

    def trigger_restart_process_jobs(self, job_applications: NameSet) -> None:
        """ Trigger the RESTART_PROCESS strategy on stored jobs.
        Stop process if necessary and defer start until process is stopped. """
        for process in list(self.restart_process_jobs):
            if process.application_name in job_applications:
                self.logger.debug(f'RunningFailureHandler.trigger_restart_process_jobs: defer {process.namespec}'
                                  ' restart')
            else:
                self.logger.info(f'RunningFailureHandler.trigger_restart_process_jobs: restarting {process.namespec}')
                self.restart_process_jobs.remove(process)
                self.supvisors.stopper.default_restart_process(process, False)

    def trigger_continue_process_jobs(self) -> None:
        """ Trigger the CONTINUE strategy on stored jobs. """
        for process in self.continue_process_jobs:
            self.logger.info('RunningFailureHandler.trigger_continue_process_jobs: continue despite failure'
                             f' of {process.namespec}')
        self.continue_process_jobs = set()

    def trigger_jobs(self):
        """ Trigger the configured strategy when a process of a running application crashes. """
        application_job_names = self.get_application_job_names()
        # consider applications to stop
        self.trigger_stop_application_jobs(application_job_names)
        # consider applications to restart
        self.trigger_restart_application_jobs(application_job_names)
        # consider processes to restart
        self.trigger_restart_process_jobs(application_job_names)
        # log only the continuation jobs
        self.trigger_continue_process_jobs()
        # global trigger
        self.supvisors.stopper.next()
        self.supvisors.starter.next()
