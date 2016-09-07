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
from supervisors.remote import *
from supervisors.options import options
from supervisors.rpcrequests import stopProcess
from supervisors.types import ConciliationStrategies, DeploymentStrategies

# Strategy management for Deployment
class _DeploymentStrategy(object):
    def getRemote(self, addresses, expectedLoading):
        raise NotImplementedError('To be implemented in subclass')

    def __isLoadingValid(self, address, expectedLoading):
        if self.__isRemoteValid(address):
            loading = context.getLoading(address)
            options.logger.debug('address={} loading={} expectedLoading={}'.format(address, loading, expectedLoading))
            return (loading + expectedLoading < 100, loading)
        options.logger.debug('address {} invalid for handling new process'.format(address))
        return (False, 0)

    def __isRemoteValid(self, address):
        if address in context.remotes.keys():
            remoteInfo = context.remotes[address] 
            options.logger.trace('address {} state={}'.format(address, remoteStateToString(remoteInfo.state)))
            return remoteInfo.state == RemoteStates.RUNNING

    def _getLoadingAndValidity(self, addresses, expectedLoading):
        # returns adresses with validity and loading
        if '*' in addresses: addresses = addressMapper.expectedAddresses
        loadingValidities = { address: self.__isLoadingValid(address, expectedLoading) for address in addresses }
        options.logger.trace('loadingValidities={}'.format(loadingValidities))
        return loadingValidities

    def _sortValidByLoading(self, loadingValidities):
        # returns adresses with validity and loading
        sortedAddresses = sorted([ (x, y[1]) for (x, y) in loadingValidities.items() if y[0] ], key=lambda (x, y): y)
        options.logger.trace('sortedAddresses={}'.format(sortedAddresses))
        return sortedAddresses


class _ConfigStrategy(_DeploymentStrategy):
    def getRemote(self, addresses, expectedLoading):
        options.logger.debug('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the first remote in list that is capable of handling the loading
        loadingValidities = self._getLoadingAndValidity(addresses, expectedLoading)
        for (address, validity) in loadingValidities.items():
            if validity[0]: return address 


class _LessLoadedStrategy(_DeploymentStrategy):
    def getRemote(self, addresses, expectedLoading):
        options.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the less loaded remote from list that is capable of handling the loading
        loadingValidities = self._getLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = self._sortValidByLoading(loadingValidities)
        return sortedAddresses[0][0]  if sortedAddresses else None


class _MostLoadedStrategy(_DeploymentStrategy):
    def getRemote(self, addresses, expectedLoading):
        options.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the most loaded remote from list that is capable of handling the loading
        loadingValidities = self._getLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = self._sortValidByLoading(loadingValidities)
        return sortedAddresses[-1][0]  if sortedAddresses else None


class _DeploymentStrategyHandler(object):
    """ Class that handles requests for deployment """

    def getStrategyInstance(self, strategy):
        """ Factory for a Deployment Strategy """
        if strategy == DeploymentStrategies.CONFIG:
            return _ConfigStrategy()
        if strategy == DeploymentStrategies.LESS_LOADED:
            return _LessLoadedStrategy()
        if strategy == DeploymentStrategies.MOST_LOADED:
            return _MostLoadedStrategy()

    def getRemote(self, strategy, addresses, expectedLoading):
        """ Creates a strategy and let it find an address to start a process having a defined loading """
        return self.getStrategyInstance(strategy).getRemote(addresses, expectedLoading)


""" Singleton for deployment strategy """
addressSelector = _DeploymentStrategyHandler()


# Strategy management for Conciliation
class _SenicideStrategy(object):
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


class _InfanticideStrategy(object):
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


class _UserStrategy(object):
    """ Strategy designed to let the user do the job """

    def conciliate(self, conflicts):
        """ Does nothing """
        pass


class _StopStrategy(object):
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


class _RestartStrategy(object):
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
            # FIXME: only master can use deployer. the marking instance is not necessarily a master
            # solution 1: 2 types of marks, one for lost, one for strategy
            # solution 2: web conciliation is only for master
            process.markForRestart = True


class _ConciliationStrategyHandler(object):
    """ Class that handles requests for conciliation """

    def getStrategyInstance(self, strategy):
        """ Factory for a Conciliation Strategy """
        if strategy == ConciliationStrategies.SENICIDE:
            return _SenicideStrategy()
        if strategy == ConciliationStrategies.INFANTICIDE:
            return _InfanticideStrategy()
        if strategy == ConciliationStrategies.USER:
            return _UserStrategy()
        if strategy == ConciliationStrategies.STOP:
            return _StopStrategy()
        if strategy == ConciliationStrategies.RESTART:
            return _RestartStrategy()

    def conciliate(self, strategy, conflicts):
        """ Creates a strategy and let it conciliate the conflicts """
        return self.getStrategyInstance(strategy).conciliate(conflicts)


""" Singleton for conciliation strategy """
conciliator = _ConciliationStrategyHandler()
