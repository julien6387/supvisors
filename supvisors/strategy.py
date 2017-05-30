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

from supvisors.ttypes import (AddressStates, ConciliationStrategies,
    DeploymentStrategies, RunningFailureStrategies)
from supvisors.utils import supvisors_short_cuts


class AbstractStrategy(object):
    """ Base class for a common constructor. """

    def __init__(self, supvisors):
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['context', 'logger'])


# Strategy management for Starting
class AbstractStartingStrategy(AbstractStrategy):
    """ Base class for a deployment strategy. """

    def is_loading_valid(self, address, expected_loading):
        """ Return True and current loading if remote Supvisors instance is active and can support the additional loading. """
        if address in self.context.addresses.keys():
            status = self.context.addresses[address] 
            self.logger.trace('address {} state={}'.format(address, status.state_string()))
            if status.state == AddressStates.RUNNING:
                loading = status.loading()
                self.logger.debug('address={} loading={} expected_loading={}'.format(address, loading, expected_loading))
                return (loading + expected_loading < 100, loading)
            self.logger.debug('address {} not RUNNING'.format(address))
        return (False, 0)

    def get_loading_and_validity(self, addresses, expected_loading):
        """ Return the report of loading capability of all addresses iaw the additional loading required. """
        if '*' in addresses:
            addresses = self.supvisors.address_mapper.addresses
        loading_validities = {address: self.is_loading_valid(address, expected_loading) for address in addresses}
        self.logger.trace('loading_validities={}'.format(loading_validities))
        return loading_validities

    def sort_valid_by_loading(self, loading_validities):
        """ Sort the loading report by loading value. """
        # returns adresses with validity and loading
        sorted_addresses = sorted([(x, y[1]) for x, y in loading_validities.items() if y[0]], key=lambda (x, y): y)
        self.logger.trace('sorted_addresses={}'.format(sorted_addresses))
        return sorted_addresses


class ConfigStrategy(AbstractStartingStrategy):
    """ Strategy designed to choose the address using the order defined in the configuration file. """

    def get_address(self, addresses, expected_loading):
        """ Choose the first address that can support the additional loading requested. """
        self.logger.debug('addresses={} expected_loading={}'.format(addresses, expected_loading))
        # returns the first remote in list that is capable of handling the loading
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        if '*' in addresses:
            addresses = self.supvisors.address_mapper.addresses
        return next((address for address in addresses if loading_validities[address][0]),  None)


class LessLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to share the loading among all the addresses. """

    def get_address(self, addresses, expected_loading):
        """ Choose the address having the lowest loading that can support the additional loading requested """
        self.logger.trace('addresses={} expectedLoading={}'.format(addresses, expected_loading))
        # returns the less loaded remote from list that is capable of handling the loading
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        sorted_addresses = self.sort_valid_by_loading(loading_validities)
        return sorted_addresses[0][0]  if sorted_addresses else None


class MostLoadedStrategy(AbstractStartingStrategy):
    """ Strategy designed to maximize the loading of an address. """

    def get_address(self, addresses, expected_loading):
        """ Choose the address having the highest loading that can support the additional loading requested """
        self.logger.trace('addresses={} expectedLoading={}'.format(addresses, expected_loading))
        # returns the most loaded remote from list that is capable of handling the loading
        loading_validities = self.get_loading_and_validity(addresses, expected_loading)
        sorted_addresses = self.sort_valid_by_loading(loading_validities)
        return sorted_addresses[-1][0]  if sorted_addresses else None


def get_address(supvisors, strategy, addresses, expected_loading):
    """ Creates a strategy and let it find an address to start a process having a defined loading. """
    if strategy == DeploymentStrategies.CONFIG:
        instance = ConfigStrategy(supvisors)
    if strategy == DeploymentStrategies.LESS_LOADED:
        instance = LessLoadedStrategy(supvisors)
    if strategy == DeploymentStrategies.MOST_LOADED:
        instance = MostLoadedStrategy(supvisors)
    # apply strategy result
    return instance.get_address(addresses, expected_loading)


# Strategy management for Conciliation
class SenicideStrategy(AbstractStrategy):
    """ Strategy designed to stop the oldest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the most recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            saved_address = min(process.addresses, key=lambda x: process.infos[x]['uptime'])
            self.logger.warn('senicide conciliation: keep {} at {}'.format(process.namespec(), saved_address))
            # stop other processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            addresses.remove(saved_address)
            for address in addresses:
                self.logger.debug('senicide conciliation: {} running on {}'.format(process.namespec(), address))
                self.supvisors.zmq.pusher.send_stop_process(address, process.namespec())


class InfanticideStrategy(AbstractStrategy):
    """ Strategy designed to stop the youngest processes. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the least recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            saved_address = max(process.addresses, key=lambda x: process.infos[x]['uptime'])
            self.logger.warn('infanticide conciliation: keep {} at {}'.format(process.namespec(), saved_address))
            # stop other processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            addresses.remove(saved_address)
            for address in addresses:
                self.logger.debug('infanticide conciliation: {} running on {}'.format(process.namespec(), address))
                self.supvisors.zmq.pusher.send_stop_process(address, process.namespec())


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
            self.logger.warn('restart conciliation: {}'.format(process.namespec()))
            # stop all processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            for address in addresses:
                self.logger.warn('stop_process requested at {}'.format(address))
                self.supvisors.zmq.pusher.send_stop_process(address, process.namespec())


class RestartStrategy(StopStrategy):
    """ Strategy designed to stop all conflicting processes
    and to re-deploy a single instance. """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by stopping all processes
        and mark the program so that the Supvisors Starter restarts it. """
        StopStrategy.conciliate(self, conflicts)
        # mark the processes to be restarted
        for process in conflicts:
            process.mark_for_restart = True


def conciliate(supvisors, strategy, conflicts):
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
    # apply strategy to conflicts
    instance.conciliate(conflicts)


# Strategy management for Running Failure
class AbstractRunningFailureStrategy(AbstractStrategy):
    """ Base class for a deployment strategy. """

    def __init__(self, supvisors):
        AbstractStrategy.__init__(self, supvisors)
        supvisors_short_cuts(self, ['starter', 'stopper'])


def on_running_failure(supvisors, strategy, application):
    """ Creates a strategy and let it conciliate the conflicts. """
    if strategy == RunningFailureStrategies.CONTINUE:
        instance = SenicideStrategy(supvisors)
    elif strategy == RunningFailureStrategies.STOP:
        instance = StopStrategy(supvisors)
    elif strategy == RunningFailureStrategies.RESTART:
        instance = UserStrategy(supvisors)
    # apply strategy to application
    instance.on_running_failure(application)

