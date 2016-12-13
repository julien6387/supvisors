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

import sys
import unittest


class TypesTest(unittest.TestCase):
    """ Test case for the types module. """

    def test_AddressStates(self):
        """ Test the AddressStates enumeration. """
        from supervisors.ttypes import AddressStates
        self.assertEqual('UNKNOWN', AddressStates._to_string(AddressStates.UNKNOWN))
        self.assertEqual('RUNNING', AddressStates._to_string(AddressStates.RUNNING))
        self.assertEqual('SILENT', AddressStates._to_string(AddressStates.SILENT))
        self.assertEqual('ISOLATING', AddressStates._to_string(AddressStates.ISOLATING))
        self.assertEqual('ISOLATED', AddressStates._to_string(AddressStates.ISOLATED))

    def test_ApplicationStates(self):
        """ Test the ApplicationStates enumeration. """
        from supervisors.ttypes import ApplicationStates
        self.assertEqual('STOPPED', ApplicationStates._to_string(ApplicationStates.STOPPED))
        self.assertEqual('STARTING', ApplicationStates._to_string(ApplicationStates.STARTING))
        self.assertEqual('RUNNING', ApplicationStates._to_string(ApplicationStates.RUNNING))
        self.assertEqual('STOPPING', ApplicationStates._to_string(ApplicationStates.STOPPING))

    def test_DeploymentStrategies(self):
        """ Test the DeploymentStrategies enumeration. """
        from supervisors.ttypes import DeploymentStrategies
        self.assertEqual('CONFIG', DeploymentStrategies._to_string(DeploymentStrategies.CONFIG))
        self.assertEqual('LESS_LOADED', DeploymentStrategies._to_string(DeploymentStrategies.LESS_LOADED))
        self.assertEqual('MOST_LOADED', DeploymentStrategies._to_string(DeploymentStrategies.MOST_LOADED))

    def test_ConciliationStrategies(self):
        """ Test the ConciliationStrategies enumeration. """
        from supervisors.ttypes import ConciliationStrategies
        self.assertEqual('SENICIDE', ConciliationStrategies._to_string(ConciliationStrategies.SENICIDE))
        self.assertEqual('INFANTICIDE', ConciliationStrategies._to_string(ConciliationStrategies.INFANTICIDE))
        self.assertEqual('USER', ConciliationStrategies._to_string(ConciliationStrategies.USER))
        self.assertEqual('STOP', ConciliationStrategies._to_string(ConciliationStrategies.STOP))
        self.assertEqual('RESTART', ConciliationStrategies._to_string(ConciliationStrategies.RESTART))

    def test_StartingFailureStrategies(self):
        """ Test the StartingFailureStrategies enumeration. """
        from supervisors.ttypes import StartingFailureStrategies
        self.assertEqual('ABORT', StartingFailureStrategies._to_string(StartingFailureStrategies.ABORT))
        self.assertEqual('CONTINUE', StartingFailureStrategies._to_string(StartingFailureStrategies.CONTINUE))

    def test_RunningFailureStrategies(self):
        """ Test the RunningFailureStrategies enumeration. """
        from supervisors.ttypes import RunningFailureStrategies
        self.assertEqual('CONTINUE', RunningFailureStrategies._to_string(RunningFailureStrategies.CONTINUE))
        self.assertEqual('STOP', RunningFailureStrategies._to_string(RunningFailureStrategies.STOP))
        self.assertEqual('RESTART', RunningFailureStrategies._to_string(RunningFailureStrategies.RESTART))

    def test_SupervisorsStates(self):
        """ Test the SupervisorsStates enumeration. """
        from supervisors.ttypes import SupervisorsStates
        self.assertEqual('INITIALIZATION', SupervisorsStates._to_string(SupervisorsStates.INITIALIZATION))
        self.assertEqual('DEPLOYMENT', SupervisorsStates._to_string(SupervisorsStates.DEPLOYMENT))
        self.assertEqual('OPERATION', SupervisorsStates._to_string(SupervisorsStates.OPERATION))
        self.assertEqual('CONCILIATION', SupervisorsStates._to_string(SupervisorsStates.CONCILIATION))

    def test_exception(self):
        """ Test the exception InvalidTransition. """
        from supervisors.ttypes import InvalidTransition
        # test with unknown attributes
        with self.assertRaises(InvalidTransition) as exc:
            raise InvalidTransition('invalid transition')
        self.assertEqual('invalid transition', exc.exception.value)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

