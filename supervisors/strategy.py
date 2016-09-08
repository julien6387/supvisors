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

from supervisors.addressmapper import addressMapper
from supervisors.context import context
from supervisors.remote import RemoteStates
from supervisors.options import options
from supervisors.rpcrequests import stopProcess
from supervisors.types import ConciliationStrategies, DeploymentStrategies


def isRemoteValid(address):
    """ Return True if remote Supervisors instance is active """
    if address in context.remotes.keys():
        remoteInfo = context.remotes[address] 
        options.logger.trace('address {} state={}'.format(address, remoteInfo.stateAsString()))
        return remoteInfo.state == RemoteStates.RUNNING

def isLoadingValid(address, expectedLoading):
    """ Return True and current loading if remote Supervisors instance is active and can suport the additional loading """
    if isRemoteValid(address):
        loading = context.getLoading(address)
        options.logger.debug('address={} loading={} expectedLoading={}'.format(address, loading, expectedLoading))
        return (loading + expectedLoading < 100, loading)
    options.logger.debug('address {} invalid for handling new process'.format(address))
    return (False, 0)

def getLoadingAndValidity(addresses, expectedLoading):
    """ Return the report of loading capability of all addresses iaw the additional loading required """
    if '*' in addresses: addresses = addressMapper.addresses
    loadingValidities = { address: isLoadingValid(address, expectedLoading) for address in addresses }
    options.logger.trace('loadingValidities={}'.format(loadingValidities))
    return loadingValidities

def sortValidByLoading(loadingValidities):
    """ Sort the loading report by loading value """
    # returns adresses with validity and loading
    sortedAddresses = sorted([ (x, y[1]) for x, y in loadingValidities.items() if y[0] ], key=lambda (x, y): y)
    options.logger.trace('sortedAddresses={}'.format(sortedAddresses))
    return sortedAddresses


class ConfigStrategy(object):
    """ Strategy designed to choose the address using the order defined in the configuration file """

    def getRemote(self, addresses, expectedLoading):
        """ Choose the first address that can support the additional loading requested """
        options.logger.debug('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the first remote in list that is capable of handling the loading
        loadingValidities = getLoadingAndValidity(addresses, expectedLoading)
        return next((address for address, validity in loadingValidities.items() if validity[0]),  None)


class LessLoadedStrategy(object):
    """ Strategy designed to share the loading among all the addresses """

    def getRemote(self, addresses, expectedLoading):
        """ Choose the address having the lowest loading that can support the additional loading requested """
        options.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the less loaded remote from list that is capable of handling the loading
        loadingValidities = getLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = sortValidByLoading(loadingValidities)
        return sortedAddresses[0][0]  if sortedAddresses else None


class MostLoadedStrategy(object):
    """ Strategy designed to maximize the loading of an address """

    def getRemote(self, addresses, expectedLoading):
        """ Choose the address having the highest loading that can support the additional loading requested """
        options.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the most loaded remote from list that is capable of handling the loading
        loadingValidities = getLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = sortValidByLoading(loadingValidities)
        return sortedAddresses[-1][0]  if sortedAddresses else None


class DeploymentStrategyHandler(object):
    """ Class that handles requests for deployment """

    def getStrategyInstance(self, strategy):
        """ Factory for a Deployment Strategy """
        if strategy == DeploymentStrategies.CONFIG:
            return ConfigStrategy()
        if strategy == DeploymentStrategies.LESS_LOADED:
            return LessLoadedStrategy()
        if strategy == DeploymentStrategies.MOST_LOADED:
            return MostLoadedStrategy()

    def getRemote(self, strategy, addresses, expectedLoading):
        """ Creates a strategy and let it find an address to start a process having a defined loading """
        return self.getStrategyInstance(strategy).getRemote(addresses, expectedLoading)


""" Singleton for deployment strategy """
addressSelector = DeploymentStrategyHandler()


# Strategy management for Conciliation
class SenicideStrategy(object):
    """ Strategy designed to stop the oldest processes """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the most recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            savedAddress = min(process.addresses, key=lambda x: process.processes[x]['uptime'])
            options.logger.warn("senicide conciliation: keep {} at {}".format(process.getNamespec(), savedAddress))
            # stop other processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            addresses.remove(savedAddress)
            for address in addresses:
                options.logger.debug("senicide conciliation: {} running on {}".format(process.getNamespec(), address))
                stopProcess(address, process.getNamespec(), False)


class InfanticideStrategy(object):
    """ Strategy designed to stop the youngest processes """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by finding the process that started the least recently and stopping the others """
        for process in conflicts:
            # determine running address with lower uptime (the youngest)
            savedAddress = max(process.addresses, key=lambda x: process.processes[x]['uptime'])
            options.logger.warn("infanticide conciliation: keep {} at {}".format(process.getNamespec(), savedAddress))
            # stop other processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            addresses.remove(savedAddress)
            for address in addresses:
                if address != savedAddress:
                    stopProcess(address, process.getNamespec(), False)


class UserStrategy(object):
    """ Strategy designed to let the user do the job """

    def conciliate(self, conflicts):
        """ Does nothing """
        pass


class StopStrategy(object):
    """ Strategy designed to stop all conflicting processes """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by stopping all processes """
        for process in conflicts:
            options.logger.warn("restart conciliation: {}".format(process.getNamespec()))
            # stop all processes. work on copy as it may change during iteration
            addresses = process.addresses.copy()
            for address in addresses:
                options.logger.warn("stopProcess requested at {}".format(address))
                stopProcess(address, process.getNamespec(), False)


class RestartStrategy(object):
    """ Strategy designed to stop all conflicting processes and to re-deploy a single instance """

    def conciliate(self, conflicts):
        """ Conciliate the conflicts by stopping all processes and mark the process so that the Supervisor deployer restarts it """
        for process in conflicts:
            options.logger.warn("restart conciliation: {}".format(process.getNamespec()))
            # work on copy as it may change during iteration
            addresses = process.addresses.copy()
            # stop all processes
            for address in addresses:
                options.logger.warn("stopProcess requested at {}".format(address))
                stopProcess(address, process.getNamespec(), False)
            # force warm restart
            # WARN: only master can use deployer
            # conciliation MUST be triggered from the Supervisors MASTER
            process.markForRestart = True


class ConciliationStrategyHandler(object):
    """ Class that handles requests for conciliation """

    def getStrategyInstance(self, strategy):
        """ Factory for a Conciliation Strategy """
        if strategy == ConciliationStrategies.SENICIDE:
            return SenicideStrategy()
        if strategy == ConciliationStrategies.INFANTICIDE:
            return InfanticideStrategy()
        if strategy == ConciliationStrategies.USER:
            return UserStrategy()
        if strategy == ConciliationStrategies.STOP:
            return StopStrategy()
        if strategy == ConciliationStrategies.RESTART:
            return RestartStrategy()

    def conciliate(self, strategy, conflicts):
        """ Creates a strategy and let it conciliate the conflicts """
        return self.getStrategyInstance(strategy).conciliate(conflicts)


""" Singleton for conciliation strategy """
conciliator = ConciliationStrategyHandler()
