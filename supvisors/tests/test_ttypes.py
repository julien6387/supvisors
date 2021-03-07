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

import sys
import unittest


class TypesTest(unittest.TestCase):
    """ Test case for the types module. """

    def test_AddressStates(self):
        """ Test the AddressStates enumeration. """
        from supvisors.ttypes import AddressStates
        self.assertEqual(['UNKNOWN', 'CHECKING', 'RUNNING', 'SILENT', 'ISOLATING', 'ISOLATED'],
                         AddressStates._member_names_)

    def test_ApplicationStates(self):
        """ Test the ApplicationStates enumeration. """
        from supvisors.ttypes import ApplicationStates
        self.assertEqual(['STOPPED', 'STARTING', 'RUNNING', 'STOPPING'],
                         ApplicationStates._member_names_)

    def test_StartingStrategies(self):
        """ Test the StartingStrategies enumeration. """
        from supvisors.ttypes import StartingStrategies
        self.assertEqual(['CONFIG', 'LESS_LOADED', 'MOST_LOADED', 'LOCAL'],
                         StartingStrategies._member_names_)

    def test_ConciliationStrategies(self):
        """ Test the ConciliationStrategies enumeration. """
        from supvisors.ttypes import ConciliationStrategies
        self.assertEqual(['SENICIDE', 'INFANTICIDE', 'USER', 'STOP', 'RESTART', 'RUNNING_FAILURE'],
                         ConciliationStrategies._member_names_)

    def test_StartingFailureStrategies(self):
        """ Test the StartingFailureStrategies enumeration. """
        from supvisors.ttypes import StartingFailureStrategies
        self.assertEqual(['ABORT', 'STOP', 'CONTINUE'],
                         StartingFailureStrategies._member_names_)

    def test_RunningFailureStrategies(self):
        """ Test the RunningFailureStrategies enumeration. """
        from supvisors.ttypes import RunningFailureStrategies
        self.assertEqual(['CONTINUE', 'RESTART_PROCESS', 'STOP_APPLICATION', 'RESTART_APPLICATION'],
                         RunningFailureStrategies._member_names_)

    def test_SupvisorsStates(self):
        """ Test the SupvisorsStates enumeration. """
        from supvisors.ttypes import SupvisorsStates
        self.assertEqual(['INITIALIZATION', 'DEPLOYMENT', 'OPERATION', 'CONCILIATION',
                          'RESTARTING', 'SHUTTING_DOWN', 'SHUTDOWN'], SupvisorsStates._member_names_)

    def test_exception(self):
        """ Test the exception InvalidTransition. """
        from supvisors.ttypes import InvalidTransition
        # test with unknown attributes
        with self.assertRaises(InvalidTransition) as exc:
            raise InvalidTransition('invalid transition')
        self.assertEqual('invalid transition', str(exc.exception))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
