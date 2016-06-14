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

from supervisors.addressmapper import *
from supervisors.context import *
from supervisors.remote import *
from supervisors.options import mainOptions as opt
from supervisors.types import DeploymentStrategies

class _Strategy(object):
    def getRemote(self, addresses, expectedLoading):
        raise NotImplementedError('To be implemented in subclass')

    def __isLoadingValid(self, address, expectedLoading):
        if self.__isRemoteValid(address):
            loading = context.getRemoteLoading(address)
            opt.logger.debug('address={} loading={} expectedLoading={}'.format(address, loading, expectedLoading))
            return (loading + expectedLoading < 100, loading)
        opt.logger.debug('address {} invalid for handling new process'.format(address))
        return (False, 0)

    def __isRemoteValid(self, address):
        if address in context.remotes.keys():
            remoteInfo = context.remotes[address] 
            opt.logger.trace('address {} state={}'.format(address, remoteStateToString(remoteInfo.state)))
            return remoteInfo.state == RemoteStates.RUNNING

    def _getRemoteLoadingAndValidity(self, addresses, expectedLoading):
        # returns adresses with validity and loading
        if '*' in addresses: addresses = addressMapper.expectedAddresses
        loadingValidities = { address: self.__isLoadingValid(address, expectedLoading) for address in addresses }
        opt.logger.trace('loadingValidities={}'.format(loadingValidities))
        return loadingValidities

    def _sortValidByLoading(self, loadingValidities):
        # returns adresses with validity and loading
        sortedAddresses = sorted([ (x, y[1]) for (x, y) in loadingValidities.items() if y[0] ], key=lambda (x, y): y)
        opt.logger.trace('sortedAddresses={}'.format(sortedAddresses))
        return sortedAddresses


class _ConfigStrategy(_Strategy):
    def getRemote(self, addresses, expectedLoading):
        opt.logger.debug('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the first remote in list that is capable of handling the loading
        loadingValidities = self._getRemoteLoadingAndValidity(addresses, expectedLoading)
        for (address, validity) in loadingValidities.items():
            if validity[0]: return address 
        return None


class _LessLoadedStrategy(_Strategy):
    def getRemote(self, addresses, expectedLoading):
        opt.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the less loaded remote from list that is capable of handling the loading
        loadingValidities = self._getRemoteLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = self._sortValidByLoading(loadingValidities)
        return sortedAddresses[0][0]  if sortedAddresses else None

class _MostLoadedStrategy(_Strategy):
    def getRemote(self, addresses, expectedLoading):
        opt.logger.trace('addresses={} expectedLoading={}'.format(addresses, expectedLoading))
        # returns the most loaded remote from list that is capable of handling the loading
        loadingValidities = self._getRemoteLoadingAndValidity(addresses, expectedLoading)
        sortedAddresses = self._sortValidByLoading(loadingValidities)
        return sortedAddresses[-1][0]  if sortedAddresses else None


class _StrategyHandler(object):
    def getStrategyInstance(self, strategy):
        if strategy == DeploymentStrategies.CONFIG:
            return _ConfigStrategy()
        if strategy == DeploymentStrategies.LESS_LOADED:
            return _LessLoadedStrategy()
        if strategy == DeploymentStrategies.MOST_LOADED:
            return _MostLoadedStrategy()
        return None

    def getRemote(self, strategy, addresses, expectedLoading):
        return self.getStrategyInstance(strategy).getRemote(addresses, expectedLoading)


addressSelector = _StrategyHandler()
