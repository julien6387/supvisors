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

from supervisors.remote import RemoteStates
from supervisors.types import ConciliationStrategies, DeploymentStrategies
from supervisors.utils import supervisors_short_cuts


class AbstractStrategy(object):
    """ Base class for a state with simple entry / next / exit actions """

    def __init__(self, supervisors):
        self.supervisors = supervisors
        supervisors_short_cuts(self, ['context', 'logger'])


class AbstractDeploymentStrategy(AbstractStrategy):
    """ Base class for a state with simple entry / next / exit actions """

    def isAddressValid(self, address):
        """ Return True if remote Supervisors instance is active """
        if address in self.context.remotes.keys():
            remoteInfo = self.context.remotes[address] 
            self.logger.trace('address {} state={}'.format(address, remoteInfo.stateAsString()))
            return remoteInfo.state == RemoteStates.RUNNING

    def isLoadingValid(self, address, expectedLoading):
        """ Return True and current loading if remote Supervisors instance is active and can suport the additional loading """
        if self.isAddressValid(address):
            loading = self.context.getLoading(address)
            self.logger.debug('address={} loading={} expectedLoading={}'.format(address, loading, expectedLoading))
            return (loading + expectedLoading < 100, loading)
        self.logger.debug('address {} invalid for handling new process'.format(address))
        return (False, 0)

    def getLoadingAndValidity(self, addresses, expectedLoading):
        """ Return the report of loading capability of all addresses iaw the additional loading required """
        if '*' in addresses:
            addresses = self.supervisors.address_mapper.addresses
        loadingValidities = { address: self.isLoadingValid(address, expectedLoading) for address in addresses }
        self.logger.trace('loadingValidities={}'.format(loadingValidities))
        return loadingValidities

    def sortValidByLoading(self, loadingValidities):
        """ Sort the loading report by loading value """
        # returns adresses with validity and loading
        sortedAddresses = sorted([ (x, y[1]) for x, y in loadingValidities.items() if y[0] ], key=lambda (x, y): y)
        self.logger.trace('sortedAddresses={}'.format(sortedAddresses))
        return sortedAddresses


class ConfigStrategy(AbstractDeploymentStrategy):
    """ Strategy designed to choose the address using the order defined in the configuration file """

    def getAddress(self, addresses, expectedLoading):
        """ Choose the first address that can support the additional loading requested """
        self.logger.debug('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the first remote in list that is capable of handling the loading
        loadingValidities = self.getLoadingAndValidity(addresses, expectedLoading)
        return next((address for address, validity in loadingValidities.items() if validity[0]),  None)


class LessLoadedStrategy(AbstractDeploymentStrategy):
    """ Strategy designed to share the loading among all the addresses """

    def getAddress(self, addresses, expectedLoading):
        """ Choose the address having the lowest loading that can support the additional loading requested """
        self.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the less loaded remote from list that is capable of handling the loading
        loadingValidities = self.getLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = self.sortValidByLoading(loadingValidities)
        return sortedAddresses[0][0]  if sortedAddresses else None


class MostLoadedStrategy(AbstractDeploymentStrategy):
    """ Strategy designed to maximize the loading of an address """

    def getAddress(self, addresses, expectedLoading):
        """ Choose the address having the highest loading that can support the additional loading requested """
        self.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the most loaded remote from list that is capable of handling the loading
        loadingValidities = self.getLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = self.sortValidByLoading(loadingValidities)
        return sortedAddresses[-1][0]  if sortedAddresses else None


def getAddress(supervisors, strategy, addresses, expectedLoading):
    """ Creates a strategy and let it find an address to start a process having a defined loading """
    if strategy == DeploymentStrategies.CONFIG:
        instance = ConfigStrategy(supervisors)
    if strategy == DeploymentStrategies.LESS_LOADED:
        instance = LessLoadedStrategy(supervisors)
    if strategy == DeploymentStrategies.MOST_LOADED:
        instance = MostLoadedStrategy(supervisors)
    # apply strategy result
    return instance.getAddress(addresses, expectedLoading)


# Strategy management for Conciliation
class SenicideStrategy(AbstractStrategy):
    """ Strategy designed to stop the oldest processes """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the most recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            savedAddress = min(process.addresses, key=lambda x: process.processes[x]['uptime'])
            self.logger.warn('senicide conciliation: keep {} at {}'.format(process.getNamespec(), savedAddress))
            # stop other processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            addresses.remove(savedAddress)
            for address in addresses:
                self.logger.debug('senicide conciliation: {} running on {}'.format(process.getNamespec(), address))
                self.supervisors.requester.stopProcess(address, process.getNamespec(), False)


class InfanticideStrategy(AbstractStrategy):
    """ Strategy designed to stop the youngest processes """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the least recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            savedAddress = max(process.addresses, key=lambda x: process.processes[x]['uptime'])
            self.logger.warn('infanticide conciliation: keep {} at {}'.format(process.getNamespec(), savedAddress))
            # stop other processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            addresses.remove(savedAddress)
            for address in addresses:
                if address != savedAddress:
                    self.supervisors.requester.stopProcess(address, process.getNamespec(), False)


class UserStrategy(AbstractStrategy):
    """ Strategy designed to let the user do the job """

    def conciliate(self, conflicts):
        """ Does nothing """
        pass


class StopStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by stopping all processes """
        for process in conflicts:
            self.logger.warn('restart conciliation: {}'.format(process.getNamespec()))
            # stop all processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            for address in addresses:
                self.logger.warn('stopProcess requested at {}'.format(address))
                self.supervisors.requester.stopProcess(address, process.getNamespec(), False)


class RestartStrategy(AbstractStrategy):
    """ Strategy designed to stop all conflicting processes and to re-deploy a single instance """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by stopping all processes and mark the process so that the Supervisor deployer restarts it """
        for process in conflicts:
            self.logger.warn('restart conciliation: {}'.format(process.getNamespec()))
            # work on copy as it may change during iteration
            addresses = process.addresses.copy()
            # stop all processes
            for address in addresses:
                self.logger.warn('stopProcess requested at {}'.format(address))
                self.supervisors.requester.stopProcess(address, process.getNamespec(), False)
            # force warm restart
            # WARN: only master can use deployer
            # conciliation MUST be triggered from the Supervisors MASTER
            process.mark_for_restart = True


def conciliate(supervisors, strategy, conflicts):
    """ Creates a strategy and let it conciliate the conflicts """
    if strategy == ConciliationStrategies.SENICIDE:
        instance = SenicideStrategy(supervisors)
    elif strategy == ConciliationStrategies.INFANTICIDE:
        instance = InfanticideStrategy(supervisors)
    elif strategy == ConciliationStrategies.USER:
        instance = UserStrategy(supervisors)
    elif strategy == ConciliationStrategies.STOP:
        instance = StopStrategy(supervisors)
    elif strategy == ConciliationStrategies.RESTART:
        instance = RestartStrategy(supervisors)
    # apply strategy to conflicts
    instance.conciliate(conflicts)
