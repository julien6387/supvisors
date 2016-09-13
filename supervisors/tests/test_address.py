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
import time
import unittest

from supervisors.tests.base import DummyLogger


class AddressTest(unittest.TestCase):
    """ Test case for the address module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.logger = DummyLogger()
        from supervisors.types import AddressStates
        self.all_states = AddressStates._values()

    def test_create(self):
        """ Test the values set at construction. """
        from supervisors.address import AddressStatus
        status = AddressStatus('66.51.20.10', self.logger)
        # test all AddressStatus values
        self.assertIs(self.logger, status.logger)
        self.assertEqual('66.51.20.10', status.address)
        from supervisors.types import AddressStates
        self.assertEqual(AddressStates.UNKNOWN, status.state)
        self.assertFalse(status.checked)
        self.assertEqual(0, status.remote_time)
        self.assertEqual(0, status.local_time)
 
    def test_isolation(self):
        """ Test the in_isolation method. """
        from supervisors.address import AddressStatus
        from supervisors.types import AddressStates
        status = AddressStatus('66.51.20.10', self.logger)
        for state in self.all_states:
            status._state = state
            self.assertTrue(status.in_isolation() and state in [AddressStates.ISOLATING, AddressStates.ISOLATED] or
                not status.in_isolation() and state not in [AddressStates.ISOLATING, AddressStates.ISOLATED])

    def test_times(self):
        """ Test the update_times method. """
        from supervisors.address import AddressStatus
        status = AddressStatus('66.51.20.10', self.logger)
        now = time.time()
        status.update_times(50, now)
        self.assertEqual(50, status.remote_time)
        self.assertEqual(now, status.local_time)

    def test_serialization(self):
        """ Test the to_json method used to get a serializable form of AddressStatus. """
        from supervisors.address import AddressStatus
        from supervisors.types import AddressStates
        # create address status instance
        status = AddressStatus('66.51.20.10', self.logger)
        status._state = AddressStates.RUNNING
        status.checked = True
        status.remote_time = 50
        status.local_time = 60
        # test to_json method
        json = status.to_json()
        self.assertEqual(sorted(['address', 'state', 'checked', 'remote_time', 'local_time']), sorted(json.keys()))
        self.assertEqual('66.51.20.10', json['address'])
        self.assertEqual('RUNNING', json['state'])
        self.assertTrue(json['checked'])
        self.assertEqual(50, json['remote_time'])
        self.assertEqual(60, json['local_time'])
        # test that returned structure is serializable using pickle
        import pickle
        serial = pickle.dumps(json)
        after_json = pickle.loads(serial)
        self.assertEqual(json, after_json)

    def test_transitions(self):
        """ Test the state transitions of AddressStatus. """
        # TODO


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
