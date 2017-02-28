#!/usr/bin/python
#-*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import sys
import unittest

from supvisors.tests.base import DummySupvisors


class StateMachinesTest(unittest.TestCase):
    """ Test case for the state classes of the statemachine module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = DummySupvisors()

    def test_abstract_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import AbstractState
        state = AbstractState(self.supvisors)
        self.assertIsNotNone(state)

    def test_initialization_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import InitializationState
        state = InitializationState(self.supvisors)
        self.assertIsNotNone(state)

    def test_deployment_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import DeploymentState
        state = DeploymentState(self.supvisors)
        self.assertIsNotNone(state)

    def test_operation_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import OperationState
        state = OperationState(self.supvisors)
        self.assertIsNotNone(state)

    def test_conciliation_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import ConciliationState
        state = ConciliationState(self.supvisors)
        self.assertIsNotNone(state)

    def test_restarting_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import RestartingState
        state = RestartingState(self.supvisors)
        self.assertIsNotNone(state)

    def test_shutting_down_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import ShuttingDownState
        state = ShuttingDownState(self.supvisors)
        self.assertIsNotNone(state)

    def test_shutdown_state(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import ShutdownState
        state = ShutdownState(self.supvisors)
        self.assertIsNotNone(state)


class FiniteStateMachineTest(unittest.TestCase):
    """ Test case for the FiniteStateMachine class of the statemachine module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = DummySupvisors()

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.statemachine import FiniteStateMachine
        state = FiniteStateMachine(self.supvisors)
        self.assertIsNotNone(state)



def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
