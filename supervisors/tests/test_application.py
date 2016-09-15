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

from supervisors.tests.base import DummyLogger


class ApplicationTest(unittest.TestCase):
    """ Test case for the application module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.logger = DummyLogger()

    def test_create(self):
        """ Test the values set at construction. """
        from supervisors.application import ApplicationStatus
        from supervisors.types import ApplicationStates, StartingFailureStrategies, RunningFailureStrategies
        application = ApplicationStatus('ApplicationTest', self.logger)
        # check application default attributes
        self.assertEqual('ApplicationTest', application.application_name)
        self.assertEqual(ApplicationStates.UNKNOWN, application.state)
        self.assertFalse(application.major_failure)
        self.assertFalse(application.minor_failure)
        self.assertFalse(application.processes)
        self.assertFalse(application.sequence)
        # check application default rules
        self.assertFalse(application.rules.autostart)
        self.assertEqual(-1, application.rules.sequence)
        self.assertEqual(StartingFailureStrategies.ABORT, application.rules.starting_failure_strategy)
        self.assertEqual(RunningFailureStrategies.CONTINUE, application.rules.running_failure_strategy)

    def test_running(self):
        """ Test the running method. """

    def test_stopped(self):
        """ Test the stopped method. """

    def test_serialization(self):
        """ Test the to_json method used to get a serializable form of Application. """

    def test_add_process(self, process):
        """ Test the add_process method. """

    def test_sequence_deployment(self):
        """ Test the sequencing of the deployment method. """

    def test_update_status(self):
        """ Test the rules to update the status of the application method. """


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

