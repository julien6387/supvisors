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

import random
import sys
import unittest

from supervisors.tests.base import DummyAddressStatus, DummySupervisors


class DeploymentStrategyTest(unittest.TestCase):
    """ Test case for the deployment strategies of the strategy module. """

    def setUp(self):
        """ Create a dummy supervisors. """
        self.supervisors = DummySupervisors()
        # add addresses to context
        from supervisors.types import AddressStates
        self.supervisors.context.addresses['10.0.0.0'] = DummyAddressStatus('10.0.0.0', AddressStates.SILENT, 0)
        self.supervisors.context.addresses['10.0.0.1'] = DummyAddressStatus('10.0.0.1', AddressStates.RUNNING, 50)
        self.supervisors.context.addresses['10.0.0.2'] = DummyAddressStatus('10.0.0.2', AddressStates.ISOLATED, 0)
        self.supervisors.context.addresses['10.0.0.3'] = DummyAddressStatus('10.0.0.3', AddressStates.RUNNING, 20)
        self.supervisors.context.addresses['10.0.0.4'] = DummyAddressStatus('10.0.0.4', AddressStates.UNKNOWN, 0)
        self.supervisors.context.addresses['10.0.0.5'] = DummyAddressStatus('10.0.0.5', AddressStates.RUNNING, 80)
        # initialize dummy address mapper with all address names (keep the alpha order)
        self.supervisors.address_mapper.addresses = sorted(self.supervisors.context.addresses.keys())

    def test_is_loading_valid(self):
        """ Test the validity of an address with an additional loading. """
        from supervisors.strategy import AbstractDeploymentStrategy
        strategy = AbstractDeploymentStrategy(self.supervisors)
        # test unknown address
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.10', 1))
        # test not RUNNING address
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.0', 1))
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.2', 1))
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.4', 1))
        # test loaded RUNNING address
        self.assertTupleEqual((False, 50), strategy.is_loading_valid('10.0.0.1', 55))
        self.assertTupleEqual((False, 20), strategy.is_loading_valid('10.0.0.3', 85))
        self.assertTupleEqual((False, 80), strategy.is_loading_valid('10.0.0.5', 25))
        # test not loaded RUNNING address
        self.assertTupleEqual((True, 50), strategy.is_loading_valid('10.0.0.1', 45))
        self.assertTupleEqual((True, 20), strategy.is_loading_valid('10.0.0.3', 75))
        self.assertTupleEqual((True, 80), strategy.is_loading_valid('10.0.0.5', 15))

    def test_get_loading_and_validity(self):
        """ Test the determination of the valid addresses with an additional loading. """
        from supervisors.strategy import AbstractDeploymentStrategy
        strategy = AbstractDeploymentStrategy(self.supervisors)
        # test valid addresses with different additional loadings
        self.assertDictEqual({'10.0.0.0': (False, 0), '10.0.0.1': (True, 50), '10.0.0.2': (False, 0), '10.0.0.3': (True, 20), '10.0.0.4': (False, 0), '10.0.0.5': (True, 80)},
            strategy.get_loading_and_validity('*', 15))
        self.assertDictEqual({'10.0.0.0': (False, 0), '10.0.0.1': (True, 50), '10.0.0.2': (False, 0), '10.0.0.3': (True, 20), '10.0.0.4': (False, 0), '10.0.0.5': (False, 80)},
            strategy.get_loading_and_validity(self.supervisors.context.addresses.keys(), 45))
        self.assertDictEqual({'10.0.0.1': (False, 50), '10.0.0.3': (True, 20), '10.0.0.5': (False, 80)},
            strategy.get_loading_and_validity(['10.0.0.1', '10.0.0.3', '10.0.0.5'], 75))
        self.assertDictEqual({'10.0.0.1': (False, 50), '10.0.0.3': (False, 20), '10.0.0.5': (False, 80)},
            strategy.get_loading_and_validity(['10.0.0.1', '10.0.0.3', '10.0.0.5'], 85))

    def test_sort_valid_by_loading(self):
        """ Test the sorting of the validities of the addresses. """
        from supervisors.strategy import AbstractDeploymentStrategy
        strategy = AbstractDeploymentStrategy(self.supervisors)
        self.assertListEqual([('10.0.0.3', 20), ('10.0.0.1', 50), ('10.0.0.5', 80)],
            strategy.sort_valid_by_loading({'10.0.0.0': (False, 0), '10.0.0.1': (True, 50), '10.0.0.2': (False, 0), '10.0.0.3': (True, 20), '10.0.0.4': (False, 0), '10.0.0.5': (True, 80)}))
        self.assertListEqual([('10.0.0.3', 20)],
            strategy.sort_valid_by_loading({'10.0.0.1': (False, 50), '10.0.0.3': (True, 20), '10.0.0.5': (False, 80)}))
        self.assertListEqual([],
            strategy.sort_valid_by_loading({'10.0.0.1': (False, 50), '10.0.0.3': (False, 20), '10.0.0.5': (False, 80)}))

    def test_config_strategy(self):
        """ Test the choice of an address according to the CONFIG strategy. """
        from supervisors.strategy import ConfigStrategy
        strategy = ConfigStrategy(self.supervisors)
        # test CONFIG strategy with different values
        self.assertEqual('10.0.0.1', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.1', strategy.get_address('*', 45))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 75))
        self.assertIsNone(strategy.get_address('*', 85))

    def test_less_loaded_strategy(self):
        """ Test the choice of an address according to the LESS_LOADED strategy. """
        from supervisors.strategy import LessLoadedStrategy
        strategy = LessLoadedStrategy(self.supervisors)
        # test LESS_LOADED strategy with different values
        self.assertEqual('10.0.0.3', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 45))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 75))
        self.assertIsNone(strategy.get_address('*', 85))

    def test_most_loaded_strategy(self):
        """ Test the choice of an address according to the MOST_LOADED strategy. """
        from supervisors.strategy import MostLoadedStrategy
        strategy = MostLoadedStrategy(self.supervisors)
        # test MOST_LOADED strategy with different values
        self.assertEqual('10.0.0.5', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.1', strategy.get_address('*', 45))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 75))
        self.assertIsNone(strategy.get_address('*', 85))

    def test_get_address(self):
        """ Test the choice of an address according to a strategy. """
        from supervisors.types import DeploymentStrategies
        from supervisors.strategy import get_address
        # test CONFIG strategy
        self.assertEqual('10.0.0.1', get_address(self.supervisors, DeploymentStrategies.CONFIG, '*', 15))
        self.assertEqual('10.0.0.3', get_address(self.supervisors, DeploymentStrategies.CONFIG, '*', 75))
        self.assertIsNone(get_address(self.supervisors, DeploymentStrategies.CONFIG, '*', 85))
        # test LESS_LOADED strategy
        self.assertEqual('10.0.0.3', get_address(self.supervisors, DeploymentStrategies.LESS_LOADED, '*', 15))
        self.assertEqual('10.0.0.3', get_address(self.supervisors, DeploymentStrategies.LESS_LOADED, '*', 75))
        self.assertIsNone(get_address(self.supervisors, DeploymentStrategies.LESS_LOADED, '*', 85))
        # test MOST_LOADED strategy
        self.assertEqual('10.0.0.5', get_address(self.supervisors, DeploymentStrategies.MOST_LOADED, '*', 15))
        self.assertEqual('10.0.0.3', get_address(self.supervisors, DeploymentStrategies.MOST_LOADED, '*', 75))
        self.assertIsNone(get_address(self.supervisors, DeploymentStrategies.MOST_LOADED, '*', 85))


class ConciliationStrategyTest(unittest.TestCase):
    """ Test case for the conciliation strategies of the strategy module. """

    def setUp(self):
        """ Create a dummy supervisors. """
        self.supervisors = DummySupervisors()
        # add processes
        # create conflicts

    def test_senicide_strategy(self):
        """ Test the strategy that consists in stopping the oldest processes. """

    def test_infanticide_strategy(self):
        """ Test the strategy that consists in stopping the youngest processes. """

    def test_user_strategy(self):
        """ Test the strategy that consists in doing nothing (trivial). """

    def test_stop_strategy(self):
        """ Test the strategy that consists in stopping all processes. """

    def test_restart_strategy(self):
        """ Test the strategy that consists in stopping all processes and restart a single one. """

    def test_conciliation(self):
        """ Test the actions on process according to a strategy. """
        from supervisors.types import ConciliationStrategies
        from supervisors.strategy import conciliate


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

