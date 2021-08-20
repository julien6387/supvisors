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

from typing import Any, Mapping, Optional, Sequence, Set, Tuple

from .application import ApplicationStatus
from .process import ProcessStatus
from .ttypes import AddressStates, NameList, ConciliationStrategies, StartingStrategies, RunningFailureStrategies

# types for annotations
LoadRequestMap = Mapping[str, int]


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
    LoadingValidity = Tuple[bool, int]
    LoadingValidityMap = Mapping[str, LoadingValidity]
    NodeLoadMap = Sequence[Tuple[str, int]]

    def is_loading_valid(self, node_name: str, expected_load: int, load_request_map: LoadRequestMap) -> LoadingValidity:
        """ Return True and current load if remote Supvisors instance is active
        and can support the additional load.

        :param node_name: the node name tested
        :param expected_load: the load to add to the node
        :param load_request_map: the unconsidered loads
        :return: a tuple with a boolean telling if the additional load is possible on node and the current load
        """
        self.logger.trace('AbstractStartingStrategy.is_loading_valid: node_name={} expected_load={} load_request_map={}'
                          .format(node_name, expected_load, load_request_map))
        if node_name in self.supvisors.context.nodes.keys():
            status = self.supvisors.context.nodes[node_name]
            self.logger.trace('AbstractStartingStrategy.is_loading_valid: node {} state={}'
                              .format(node_name, status.state.name))
            if status.state == AddressStates.RUNNING:
                loading = status.get_loading() + load_request_map.get(node_name, 0)
                self.logger.debug('AbstractStartingStrategy.is_loading_valid: node_name={} loading={} expected_load={}'
                                  .format(node_name, loading, expected_load))
                return loading + expected_load <= 100, loading
            self.logger.trace('AbstractStartingStrategy.is_loading_valid: node {} not RUNNING'.format(node_name))
        return False, 0

    def get_loading_and_validity(self, node_names: NameList, expected_load: int,
                                 load_request_map: LoadRequestMap) -> LoadingValidityMap:
        """ Return the report of loading capability of all nodes iaw the additional load required.

        :param node_names: the nodes considered
        :param expected_load: the additional load to consider for the program to be started
        :param load_request_map: the unconsidered loads
        :return: the list of nodes that can hold the additional load
        """
        loading_validity_map = {node_name: self.is_loading_valid(node_name, expected_load, load_request_map)
                                for node_name in node_names}
        self.logger.trace('AbstractStartingStrategy.get_loading_and_validity: loading_validity_map={}'
                          .format(loading_validity_map))
        return loading_validity_map

    def sort_valid_by_loading(self, loading_validity_map: LoadingValidityMap) -> NodeLoadMap:
        """ Sort the loading report by loading value. """
        # returns nodes with validity and loading
        sorted_nodes = sorted([(x, y[1])
                               for x, y in loading_validity_map.items()
                               if y[0]], key=lambda t: t[1])
        self.logger.trace('AbstractStartingStrategy.sort_valid_by_loading: sorted_nodes={}'.format(sorted_nodes))
        return sorted_nodes

    def get_node(self, node_names: NameList, expected_load: int, load_request_map: LoadRequestMap) -> Optional[str]:
        """ Choose the node that can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in AddressStatus.

        :param node_names: the candidate nodes
        :param expected_load: the load of the program to be started
        :param load_request_map: the unconsidered loads
        :return: the list of nodes that can hold the additional load
        """
        raise NotImplementedError


class ConfigStrategy(AbstractStartingStrategy):
    """ Strategy designed to choose the node using the order defined in the configuration file. """

    def get_node(self, node_names: NameList, expected_load: int, load_request_map: LoadRequestMap) -> Optional[str]:
        """ Choose the first node in the list that can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in AddressStatus.

        :param node_names: the candidate nodes
        :param expected_load: the load of the program to be started
        :param load_request_map: the unconsidered loads
        :return: the list of nodes that can hold the additional load
        """
        self.logger.debug('ConfigStrategy.get_node: node_names={} expected_load={} request_map={}'
                          .format(node_names, expected_load, load_request_map))
        loading_validity_map = self.get_loading_and_validity(node_names, expected_load, load_request_map)
        return next((node_name for node_name, (validity, _) in loading_validity_map.items() if validity), None)


class LessLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to share the loading among all the nodes. """

    def get_node(self, node_names: NameList, expected_load: int, load_request_map: LoadRequestMap) -> Optional[str]:
        """ Choose the node having the lowest loading that can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in AddressStatus.

        :param node_names: the candidate nodes
        :param expected_load: the load of the program to be started
        :param load_request_map: the unconsidered loads
        :return: the list of nodes that can hold the additional load
        """
        self.logger.trace('LessLoadedStrategy.get_node: node_names={} expected_load={} request_map={}'
                          .format(node_names, expected_load, load_request_map))
        loading_validity_map = self.get_loading_and_validity(node_names, expected_load, load_request_map)
        sorted_nodes = self.sort_valid_by_loading(loading_validity_map)
        return sorted_nodes[0][0] if sorted_nodes else None


class MostLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to maximize the loading of a node. """

    def get_node(self, node_names: NameList, expected_load: int, load_request_map: LoadRequestMap) -> Optional[str]:
        """ Choose the node having the highest loading that can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in AddressStatus.

        :param node_names: the candidate nodes
        :param expected_load: the load of the program to be started
        :param load_request_map: the unconsidered loads
        :return: the list of nodes that can hold the additional load
        """
        self.logger.trace('MostLoadedStrategy: node_names={} expected_load={} load_request_map={}'
                          .format(node_names, expected_load, load_request_map))
        loading_validity_map = self.get_loading_and_validity(node_names, expected_load, load_request_map)
        sorted_nodes = self.sort_valid_by_loading(loading_validity_map)
        return sorted_nodes[-1][0] if sorted_nodes else None


class LocalStrategy(AbstractStartingStrategy):
    """ Strategy designed to start the process on the local node. """

    def get_node(self, node_names: NameList, expected_load: int, load_request_map: LoadRequestMap) -> Optional[str]:
        """ Choose the local node provided that it can support the additional load requested.
        The load of the processes that have just been requested to start are to be considered separately because they
        are not considered yet in AddressStatus.

        :param node_names: the candidate nodes
        :param expected_load: the load of the program to be started
        :param load_request_map: the unconsidered loads
        :return: the list of nodes that can hold the additional load
        """
        self.logger.trace('LocalStrategy: node_names={} expected_load={} load_request_map={}'
                          .format(node_names, expected_load, load_request_map))
        loading_validity_map = self.get_loading_and_validity(node_names, expected_load, load_request_map)
        local_node_name = self.supvisors.address_mapper.local_node_name
        return local_node_name if loading_validity_map.get(local_node_name, (False,))[0] else None


def get_node(supvisors: Any, strategy: StartingStrategies, node_rules: NameList, expected_load: int,
             load_request_map: LoadRequestMap) -> Optional[str]:
    """ Creates a strategy and let it find a node to start a process having a defined load. """
    instance = None
    if strategy == StartingStrategies.CONFIG:
        instance = ConfigStrategy(supvisors)
    if strategy == StartingStrategies.LESS_LOADED:
        instance = LessLoadedStrategy(supvisors)
    if strategy == StartingStrategies.MOST_LOADED:
        instance = MostLoadedStrategy(supvisors)
    if strategy == StartingStrategies.LOCAL:
        instance = LocalStrategy(supvisors)
    # apply strategy result
    return instance.get_node(node_rules, expected_load, load_request_map) if instance else None


# Strategy management for Conciliation
class SenicideStrategy(AbstractStrategy):
    """ Strategy designed to stop the oldest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the most recently and stopping the others """
        for process in conflicts:
            # determine running node with lower uptime (the youngest)
            # uptime is used as there is guarantee that nodes are time synchronized
            # so comparing start dates may be irrelevant
            saved_node = min(process.running_nodes, key=lambda x: process.info_map[x]['uptime'])
            self.logger.warn('SenicideStrategy.conciliate: keep {} at {}'.format(process.namespec, saved_node))
            # stop other processes. work on copy as it may change during iteration
            # Stopper can't be used here as it would stop all processes
            running_nodes = process.running_nodes.copy()
            running_nodes.remove(saved_node)
            for node_name in running_nodes:
                self.logger.debug('SenicideStrategy.conciliate: {} running on {}'.format(process.namespec, node_name))
                self.supvisors.zmq.pusher.send_stop_process(node_name, process.namespec)


class InfanticideStrategy(AbstractStrategy):
    """ Strategy designed to stop the youngest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the least recently and stopping the others """
        for process in conflicts:
            # determine running node with lower uptime (the youngest)
            saved_node = max(process.running_nodes, key=lambda x: process.info_map[x]['uptime'])
            self.logger.warn('InfanticideStrategy.conciliate: keep {} at {}'.format(process.namespec, saved_node))
            # stop other processes. work on copy as it may change during iteration
            # Stopper can't be used here as it would stop all processes
            running_nodes = process.running_nodes.copy()
            running_nodes.remove(saved_node)
            for node_name in running_nodes:
                self.logger.debug('InfanticideStrategy.conciliate: {} running on {}'
                                  .format(process.namespec, node_name))
                self.supvisors.zmq.pusher.send_stop_process(node_name, process.namespec)


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
            self.logger.warn('StopStrategy.conciliate: {}'.format(process.namespec))
            self.supvisors.stopper.stop_process(process)


class RestartStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes and to restart a single instance. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by notifying the failure handler to restart the process. """
        # add all processes to be restarted to the failure handler,
        # as it is in its design to restart a process
        for process in conflicts:
            self.logger.warn('RestartStrategy.conciliate: {}'.format(process.namespec))
            self.supvisors.failure_handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process)
        # trigger the jobs of the failure handler directly (could wait for next tick)
        self.supvisors.failure_handler.trigger_jobs()


class FailureStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes and to apply the running failure strategy
    related to the process. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by notifying the failure handler to apply the running failure strategy
        related to the process. """
        # stop all processes and add them to the failure handler
        for process in conflicts:
            self.supvisors.stopper.stop_process(process)
            self.logger.warn('FailureStrategy.conciliate: {}'.format(process.namespec))
            self.supvisors.failure_handler.add_default_job(process)
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

        - stop_application_jobs: the set of application names to be stopped,
        - restart_application_jobs: the set of application names to be restarted,
        - restart_process_jobs: the set of processes to be restarted.
        - continue_process_jobs: the set of processes to be ignored (only for log).
        - start_application_jobs: the set of application to be started (deferred job).
        - start_process_jobs: the set of processes to be started (deferred job).
    """

    def __init__(self, supvisors):
        AbstractStrategy.__init__(self, supvisors)
        # the initial jobs
        self.stop_application_jobs: Set[ApplicationStatus] = set()
        self.restart_application_jobs: Set[ApplicationStatus] = set()
        self.restart_process_jobs: Set[ProcessStatus] = set()
        self.continue_process_jobs: Set[ProcessStatus] = set()
        # the deferred jobs
        self.start_application_jobs: Set[ApplicationStatus] = set()
        self.start_process_jobs: Set[ProcessStatus] = set()

    def abort(self):
        """ Clear all sets. """
        self.stop_application_jobs = set()
        self.restart_application_jobs = set()
        self.restart_process_jobs = set()
        self.continue_process_jobs = set()
        self.start_application_jobs = set()
        self.start_process_jobs = set()

    def add_stop_application_job(self, application: ApplicationStatus) -> None:
        """ Add the application name to the stop_application_jobs, checking if this job supersedes other jobs.

        :param application: the application to stop due to a failed process
        :return: None
        """
        self.logger.info('RunningFailureHandler.add_stop_application_job: adding {}'
                         .format(application.application_name))
        self.stop_application_jobs.add(application)
        # stop_application_jobs take precedence over all other jobs related to this application
        self.restart_application_jobs.discard(application)
        self.start_application_jobs.discard(application)
        for job_set in [self.restart_process_jobs, self.start_process_jobs, self.continue_process_jobs]:
            for process in list(job_set):
                if process.application_name == application.application_name:
                    job_set.discard(process)

    def add_restart_application_job(self, application: ApplicationStatus) -> None:
        """ Add the application name to the restart_application_jobs, checking if this job supersedes other jobs
        and assuming that stop_application_jobs and start_application_jobs (deferred restart) take precedence
        over restart_application_jobs.

        :param application: the application to restart due to a failed process
        :return: None
        """
        if application in self.stop_application_jobs | self.start_application_jobs:
            self.logger.info('RunningFailureHandler.add_restart_application_job: {} not added because already'
                             ' in stop_application_jobs or start_application_jobs'
                             .format(application.application_name))
            return
        self.logger.info('RunningFailureHandler.add_restart_application_job: adding {}'
                         .format(application.application_name))
        self.restart_application_jobs.add(application)
        # restart_application_jobs take precedence over all process jobs
        # remove only processes that are declared in the application start sequence
        sequenced_processes = application.get_start_sequenced_processes()
        for job_set in [self.restart_process_jobs, self.start_process_jobs, self.continue_process_jobs]:
            for process in list(job_set):
                if process.application_name == application.application_name and process in sequenced_processes:
                    job_set.remove(process)

    def add_restart_process_job(self, application: ApplicationStatus, process: ProcessStatus) -> None:
        """ Add the process to the restart_process_jobs, checking if this job supersedes other jobs and assuming that:
            * stop_application_jobs takes precedence over restart_process_jobs ;
            * restart_application_jobs takes precedence over restart_process_jobs if the process is in the application
              starting sequence ;
            * start_application_jobs (deferred application restart) takes precedence over restart_process_jobs ;
            * start_process_jobs (deferred process restart) takes precedence over restart_process_jobs.

        :param application: the application including the failed process to restart
        :param process: the failed process to restart
        :return: None
        """
        if application in self.stop_application_jobs:
            self.logger.info('RunningFailureHandler.add_restart_process_job: {} not added because {} already'
                             ' in stop_application_jobs'.format(process.namespec, process.application_name))
            return
        if application in self.restart_application_jobs | self.start_application_jobs:
            if process in application.get_start_sequenced_processes():
                self.logger.info('RunningFailureHandler.add_restart_process_job: {} not added because {} already'
                                 ' in restart_application_jobs or start_application_jobs'
                                 .format(process.namespec, process.application_name))
                return
        if process in self.start_process_jobs:
            self.logger.info('RunningFailureHandler.add_continue_process_job: {} not added because already'
                             ' in start_process_jobs'.format(process.namespec))
            return
        self.logger.info('RunningFailureHandler.add_restart_process_job: adding {}'.format(process.namespec))
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
            self.logger.info('RunningFailureHandler.add_continue_process_job: {} not added because {} already'
                             ' in stop_application_jobs'.format(process.namespec, process.application_name))
            return
        if application in self.restart_application_jobs | self.start_application_jobs:
            if process in application.get_start_sequenced_processes():
                self.logger.info('RunningFailureHandler.add_continue_process_job: {} not added because already'
                                 ' in stop_application_jobs'.format(process.namespec, process.application_name))
                return
        if process in self.restart_process_jobs | self.start_process_jobs:
            self.logger.info('RunningFailureHandler.add_continue_process_job: {} not added because already'
                             ' in restart_process_jobs or start_process_jobs'.format(process.namespec))
            return
        self.logger.info('RunningFailureHandler.add_continue_process_job: adding {}'.format(process.namespec))
        self.continue_process_jobs.add(process)

    def add_job(self, strategy, process):
        """ Add a process or the related application name in the relevant set,
        iaw the strategy set in parameter and the priorities defined above. """
        self.logger.trace('RunningFailureHandler.add_job: START stop_application_jobs={} restart_application_jobs={}'
                          ' restart_process_jobs={} continue_process_jobs={}'
                          ' start_application_jobs={} start_process_jobs={}'
                          .format(self.stop_application_jobs, self.restart_application_jobs, self.restart_process_jobs,
                                  self.continue_process_jobs, self.start_application_jobs, self.start_process_jobs))
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
        self.logger.trace('RunningFailureHandler.add_job: END stop_application_jobs={} restart_application_jobs={}'
                          ' restart_process_jobs={} continue_process_jobs={}'
                          ' start_application_jobs={} start_process_jobs={}'
                          .format(self.stop_application_jobs, self.restart_application_jobs, self.restart_process_jobs,
                                  self.continue_process_jobs, self.start_application_jobs, self.start_process_jobs))

    def add_default_job(self, process: ProcessStatus):
        """ Add a process or the related application name in the relevant set,
        iaw the strategy set in process rules and the priorities defined above. """
        self.add_job(process.rules.running_failure_strategy, process)
        # check strategy promotion
        if process.rules.running_failure_strategy == RunningFailureStrategies.RESTART_PROCESS:
            # this is the case where the node has been invalidated
            # if the application is stopped due to such failure, it is likely that the full application needs a restart
            # rather than uncorrelated process restarts
            application = self.supvisors.context.applications[process.application_name]
            if application.stopped() and process in application.get_start_sequenced_processes():
                # promote to RESTART_APPLICATION if process is in application start_sequence
                # the job that has just been added will be swiped out as this strategy takes precedence
                self.logger.warn('RunningFailureHandler.add_default_job: program={} with strategy=RESTART_PROCESS'
                                 ' in an application stopped will use a promoted strategy=RESTART_APPLICATION'
                                 .format(process.namespec))
                self.add_job(RunningFailureStrategies.RESTART_APPLICATION, process)

    def get_job_applications(self) -> Set[str]:
        """ Get all application names involved in Commanders.

        :return: the list of application names
        """
        return self.supvisors.starter.get_job_applications() | self.supvisors.stopper.get_job_applications()

    def trigger_stop_application_jobs(self, job_applications: Set[str]) -> None:
        """ Trigger the STOP_APPLICATION strategy on stored jobs. """
        for application in list(self.stop_application_jobs):
            if application.application_name in job_applications:
                self.logger.debug('RunningFailureHandler.trigger_stop_application_jobs: {} stop deferred'
                                  .format(application.application_name))
            else:
                self.logger.info('RunningFailureHandler.trigger_stop_application_jobs: stopping {}'
                                 .format(application.application_name))
                self.stop_application_jobs.remove(application)
                self.supvisors.stopper.stop_application(application)

    def trigger_restart_application_jobs(self, job_applications: Set[str]) -> None:
        """ Trigger the RESTART_APPLICATION strategy on stored jobs.
        Stop application if necessary and defer start until application is fully stopped. """
        for application in list(self.restart_application_jobs):
            if application.application_name in job_applications:
                self.logger.debug('RunningFailureHandler.trigger_restart_application_jobs: {} restart deferred'
                                  .format(application.application_name))
            else:
                self.logger.warn('RunningFailureHandler.trigger_restart_application_jobs: stopping {}'
                                 .format(application.application_name))
                self.restart_application_jobs.remove(application)
                # first stop the application
                self.supvisors.stopper.stop_application(application)
                # defer the application starting
                self.start_application_jobs.add(application)

    def trigger_restart_process_jobs(self, job_applications: Set[str]) -> None:
        """ Trigger the RESTART_PROCESS strategy on stored jobs.
        Stop process if necessary and defer start until process is stopped. """
        for process in list(self.restart_process_jobs):
            if process.application_name in job_applications:
                self.logger.debug('RunningFailureHandler.trigger_restart_process_jobs: {} restart deferred'
                                  .format(process.namespec))
            else:
                self.logger.info('RunningFailureHandler.trigger_restart_process_jobs: stopping {}'
                                 .format(process.namespec))
                self.restart_process_jobs.remove(process)
                self.supvisors.stopper.stop_process(process)
                # defer the process starting
                self.start_process_jobs.add(process)

    def trigger_start_application_jobs(self, job_applications: Set[str]) -> None:
        """ Trigger the deferred start of RESTART_APPLICATION strategy on stored jobs. """
        for application in list(self.start_application_jobs):
            if application.stopped() and application.application_name not in job_applications:
                self.logger.info('RunningFailureHandler.trigger_start_application_jobs: starting {}'
                                 .format(application.application_name))
                self.start_application_jobs.remove(application)
                self.supvisors.starter.default_start_application(application)
            else:
                self.logger.debug('RunningFailureHandler.trigger_start_application_jobs: {} start deferred'
                                  .format(application.application_name))

    def trigger_start_process_jobs(self, job_applications: Set[str]) -> None:
        """ Trigger the deferred start of RESTART_PROCESS strategy on stored jobs. """
        for process in list(self.start_process_jobs):
            if process.stopped() and process.application_name not in job_applications:
                self.logger.warn('RunningFailureHandler.trigger_start_process_jobs: starting {}'
                                 .format(process.namespec))
                self.start_process_jobs.remove(process)
                self.supvisors.starter.default_start_process(process)
            else:
                self.logger.debug('RunningFailureHandler.trigger_start_process_jobs: {} start deferred'
                                  .format(process.namespec))

    def trigger_continue_process_jobs(self) -> None:
        """ Trigger the CONTINUE strategy on stored jobs. """
        for process in self.continue_process_jobs:
            self.logger.info('RunningFailureHandler.trigger_continue_process_jobs: continue despite failure of {}'
                             .format(process.namespec))
        self.continue_process_jobs = set()

    def trigger_jobs(self):
        """ Trigger the configured strategy when a process of a running application crashes. """
        job_applications = self.get_job_applications()
        # consider applications to stop
        self.trigger_stop_application_jobs(job_applications)
        # consider applications to restart
        self.trigger_restart_application_jobs(job_applications)
        # consider processes to restart
        self.trigger_restart_process_jobs(job_applications)
        # consider applications to start
        self.trigger_start_application_jobs(job_applications)
        # consider processes to start
        self.trigger_start_process_jobs(job_applications)
        # log only the continuation jobs
        self.trigger_continue_process_jobs()
