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

from supvisors.ttypes import (AddressStates,
                              ConciliationStrategies,
                              StartingStrategies,
                              RunningFailureStrategies)
from supvisors.utils import supvisors_shortcuts


class AbstractStrategy(object):
    """ Base class for a common constructor. """

    def __init__(self, supvisors):
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['address_mapper', 'context', 'logger'])


# Strategy management for Starting
class AbstractStartingStrategy(AbstractStrategy):
    """ Base class for a starting strategy. """

    def is_loading_valid(self, address, expected_loading):
        """ Return True and current loading if remote Supvisors instance is active
        and can support the additional loading. """
        self.logger.trace('is_loading_valid address={} expected_loading={}'.format(address, expected_loading))
        if address in self.context.addresses.keys():
            status = self.context.addresses[address]
            self.logger.trace('address {} state={}'.format(address, status.state_string()))
            if status.state == AddressStates.RUNNING:
                loading = status.loading()
                self.logger.debug('address={} loading={} expected_loading={}'
                                  .format(address, loading, expected_loading))
                return loading + expected_loading < 100, loading
            self.logger.trace('address {} not RUNNING'.format(address))
        return False, 0

    def get_loading_and_validity(self, addresses, expected_loading):
        """ Return the report of loading capability of all addresses iaw the additional loading required. """
        if '*' in addresses:
            addresses = self.address_mapper.addresses
        loading_validities = {address: self.is_loading_valid(address, expected_loading)
                              for address in addresses}
        self.logger.trace('loading_validities={}'.format(loading_validities))
        return loading_validities

    def sort_valid_by_loading(self, loading_validities):
        """ Sort the loading report by loading value. """
        # returns adresses with validity and loading
        sorted_addresses = sorted([(x, y[1])
                                   for x, y in loading_validities.items()
                                   if y[0]], key=lambda t: t[1])
        self.logger.trace('sorted_addresses={}'.format(sorted_addresses))
        return sorted_addresses


class ConfigStrategy(AbstractStartingStrategy):
    """ Strategy designed to choose the address using the order defined in the configuration file. """

    def get_address(self, addresses, expected_loading):
        """ Choose the first address that can support the additional loading requested. """
        self.logger.debug('ConfigStrategy: addresses={} expected_loading={}'
                          .format(addresses, expected_loading))
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        return next((address for address, (validity, _) in loading_validities.items() if validity), None)


class LessLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to share the loading among all the addresses. """

    def get_address(self, addresses, expected_loading):
        """ Choose the address having the lowest loading that can support the additional loading requested. """
        self.logger.trace('LessLoadedStrategy: addresses={} expectedLoading={}'.format(addresses, expected_loading))
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        sorted_addresses = self.sort_valid_by_loading(loading_validities)
        return sorted_addresses[0][0] if sorted_addresses else None


class MostLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to maximize the loading of an address. """

    def get_address(self, addresses, expected_loading):
        """ Choose the address having the highest loading that can support the additional loading requested. """
        self.logger.trace('MostLoadedStrategy: addresses={} expectedLoading={}'.format(addresses, expected_loading))
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        sorted_addresses = self.sort_valid_by_loading(loading_validities)
        return sorted_addresses[-1][0] if sorted_addresses else None


class LocalStrategy(AbstractStartingStrategy):
    """ Strategy designed to start the process on the local address. """

    def get_address(self, addresses, expected_loading):
        """ Choose the local address provided that it can support the additional loading requested. """
        self.logger.trace('LocalStrategy: addresses={} expectedLoading={}'.format(addresses, expected_loading))
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        local_address = self.address_mapper.local_address
        return local_address if loading_validities.get(local_address, (False,))[0] else None


def get_address(supvisors, strategy, addresses, expected_loading):
    """ Creates a strategy and let it find an address to start a process having a defined loading. """
    if strategy == StartingStrategies.CONFIG:
        instance = ConfigStrategy(supvisors)
    if strategy == StartingStrategies.LESS_LOADED:
        instance = LessLoadedStrategy(supvisors)
    if strategy == StartingStrategies.MOST_LOADED:
        instance = MostLoadedStrategy(supvisors)
    if strategy == StartingStrategies.LOCAL:
        instance = LocalStrategy(supvisors)
    # apply strategy result
    return instance.get_address(addresses, expected_loading)


# Strategy management for Conciliation
class SenicideStrategy(AbstractStrategy):
    """ Strategy designed to stop the oldest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the
        most recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            # uptime is used as there is guarantee that addresses are time synchonized
            # so comparing start dates may be irrelevant
            saved_address = min(process.addresses,
                                key=lambda x: process.infos[x]['uptime'])
            self.logger.warn('senicide conciliation: keep {} at {}'.format(
                process.namespec(), saved_address))
            # stop other processes. work on copy as it may change during iteration
            # Stopper can't be used here as it would stop all processes
            addresses = process.addresses.copy()
            addresses.remove(saved_address)
            for address in addresses:
                self.logger.debug('senicide conciliation: {} running on {}'
                                  .format(process.namespec(), address))
                self.supvisors.zmq.pusher.send_stop_process(
                    address, process.namespec())


class InfanticideStrategy(AbstractStrategy):
    """ Strategy designed to stop the youngest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the
        least recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            saved_address = max(process.addresses,
                                key=lambda x: process.infos[x]['uptime'])
            self.logger.warn('infanticide conciliation: keep {} at {}'
                             .format(process.namespec(), saved_address))
            # stop other processes. work on copy as it may change during iteration
            # Stopper can't be used here as it would stop all processes
            addresses = process.addresses.copy()
            addresses.remove(saved_address)
            for address in addresses:
                self.logger.debug('infanticide conciliation: {} running on {}'
                                  .format(process.namespec(), address))
                self.supvisors.zmq.pusher.send_stop_process(
                    address, process.namespec())


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
            self.logger.warn('stop conciliation: {}'.format(process.namespec()))
            self.supvisors.stopper.stop_process(process)


class RestartStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes and to restart a single instance. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by notifying the failure handler to restart the process. """
        # add all processes to be restarted to the failure handler,
        # as it is in its design to restart a process
        for process in conflicts:
            self.logger.warn('restart conciliation: {}'.format(process.namespec()))
            self.supvisors.failure_handler.add_job(
                RunningFailureStrategies.RESTART_PROCESS, process)
        # trigger the jobs of the failure handler directly (could wait for
        # next tick)
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
            self.logger.warn('FailureStrategy.conciliate: failure conciliation: {}'.format(process.namespec()))
            self.supvisors.failure_handler.add_default_job(process)
        # trigger the jobs of the failure handler directly (could wait for next tick)
        self.supvisors.failure_handler.trigger_jobs()


def conciliate_conflicts(supvisors, strategy, conflicts):
    """ Creates a strategy and let it conciliate the conflicts. """
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
        supvisors_shortcuts(self, ['starter', 'stopper'])
        # the initial jobs
        self.stop_application_jobs = set()
        self.restart_application_jobs = set()
        self.restart_process_jobs = set()
        self.continue_process_jobs = set()
        # the deferred jobs
        self.start_application_jobs = set()
        self.start_process_jobs = set()

    def clear_jobs(self):
        """ Clear all sets. """
        self.stop_application_jobs = set()
        self.restart_application_jobs = set()
        self.restart_process_jobs = set()
        self.continue_process_jobs = set()
        self.start_application_jobs = set()
        self.start_process_jobs = set()

    def add_job(self, strategy, process):
        """ Add a process or the related application name in the relevant set,
        iaw the strategy set in parameter and the priorities defined above. """
        application_name = process.application_name
        if strategy == RunningFailureStrategies.STOP_APPLICATION:
            self.stop_application_jobs.add(application_name)
            self.restart_application_jobs = set(filter(lambda x: x != application_name,
                                                       self.restart_application_jobs))
            self.restart_process_jobs = set(filter(lambda x: x.application_name != application_name,
                                                   self.restart_process_jobs))
            self.continue_process_jobs = set(filter(lambda x: x.application_name != application_name,
                                                    self.continue_process_jobs))
        elif strategy == RunningFailureStrategies.RESTART_APPLICATION:
            if application_name not in self.stop_application_jobs:
                self.restart_application_jobs.add(application_name)
                self.restart_process_jobs = set(filter(lambda x: x.application_name != application_name,
                                                       self.restart_process_jobs))
                self.continue_process_jobs = set(filter(lambda x: x.application_name != application_name,
                                                        self.continue_process_jobs))
        elif strategy == RunningFailureStrategies.RESTART_PROCESS:
            if application_name not in self.stop_application_jobs and \
                    application_name not in self.restart_application_jobs:
                self.restart_process_jobs.add(process)
                self.continue_process_jobs.discard(process)
        elif strategy == RunningFailureStrategies.CONTINUE:
            if application_name not in self.stop_application_jobs and \
                    application_name not in self.restart_application_jobs and \
                    process not in self.restart_process_jobs:
                self.continue_process_jobs.add(process)

    def add_default_job(self, process):
        """ Add a process or the related application name in the relevant set,
        iaw the strategy set in process rules and the priorities defined above. """
        self.add_job(process.rules.running_failure_strategy, process)

    def trigger_jobs(self):
        """ Trigger the configured strategy when a process of a running application crashes. """
        # consider applications to stop
        if self.stop_application_jobs:
            for application_name in self.stop_application_jobs:
                self.logger.warn('RunningFailureHandler.trigger_jobs: stop application {}'
                                 .format(application_name))
                application = self.context.applications[application_name]
                self.stopper.stop_application(application)
            self.stop_application_jobs = set()
        # consider applications to restart
        if self.restart_application_jobs:
            for application_name in self.restart_application_jobs:
                self.logger.warn('RunningFailureHandler.trigger_jobs: restart application {}'
                                 .format(application_name))
                application = self.context.applications[application_name]
                self.stopper.stop_application(application)
                # defer the application starting
                self.start_application_jobs.add(application)
            self.restart_application_jobs = set()
        # consider processes to restart
        if self.restart_process_jobs:
            for process in self.restart_process_jobs:
                self.logger.warn('RunningFailureHandler.trigger_jobs: restart process {}'
                                 .format(process.namespec()))
                self.stopper.stop_process(process)
                # defer the process starting
                self.start_process_jobs.add(process)
            self.restart_process_jobs = set()
        # consider applications to start
        if self.start_application_jobs:
            for application in self.start_application_jobs.copy():
                if application.stopped():
                    self.logger.debug('RunningFailureHandler.trigger_jobs: start application {}'
                                      .format(application.application_name))
                    self.starter.default_start_application(application)
                    self.start_application_jobs.remove(application)
        # consider processes to start
        if self.start_process_jobs:
            for process in self.start_process_jobs.copy():
                if process.stopped():
                    self.logger.warn('RunningFailureHandler.trigger_jobs: start process {}'
                                     .format(process.namespec()))
                    self.starter.default_start_process(process)
                    self.start_process_jobs.remove(process)
        # log only the continuation jobs
        if self.continue_process_jobs:
            for process in self.continue_process_jobs:
                self.logger.info('RunningFailureHandler.trigger_jobs: continue despite of crashed process {}'
                                 .format(process.namespec()))
            self.continue_process_jobs = set()
