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

from supervisors.tests.base import (DummyLogger,
    any_process_info, any_stopped_process_info, any_running_process_info,
    process_info_by_name, any_process_info_by_state)


class ProcessTest(unittest.TestCase):
    """ Test case for the process module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.logger = DummyLogger()

    def test_create(self):
        """ Test the values set at construction. """
        from supervisors.process import ProcessStatus
        # test with stopped process
        info = any_stopped_process_info()
        process = ProcessStatus('10.0.0.1', info, self.logger)
        # check application default attributes
        self.assertIs(self.logger, process.logger)
        self.assertEqual(info['group'], process.application_name)
        self.assertEqual(info['name'], process.process_name)
        self.assertEqual(info['state'], process.state)
        self.assertEqual(not info['spawnerr'], process.expected_exit)
        self.assertEqual(info['now'], process.last_event_time)
        self.assertFalse(process.mark_for_restart)
        self.assertFalse(process.ignore_wait_exit)
        self.assertFalse(process.addresses)
        self.assertListEqual(['10.0.0.1'], process.infos.keys())
        process_info = process.infos['10.0.0.1']
        self.assertEqual(process_info['event_time'], process_info['now'])
        self.assertEqual(0, process_info['pid'])
        # test with running process
        info = any_running_process_info()
        process = ProcessStatus('10.0.0.1', info, self.logger)
        # check application default attributes
        self.assertIs(self.logger, process.logger)
        self.assertEqual(info['group'], process.application_name)
        self.assertEqual(info['name'], process.process_name)
        self.assertEqual(info['state'], process.state)
        self.assertEqual(not info['spawnerr'], process.expected_exit)
        self.assertEqual(info['now'], process.last_event_time)
        self.assertFalse(process.mark_for_restart)
        self.assertFalse(process.ignore_wait_exit)
        self.assertListEqual(['10.0.0.1'], list(process.addresses))
        self.assertListEqual(['10.0.0.1'], process.infos.keys())
        process_info = process.infos['10.0.0.1']
        self.assertEqual(process_info['event_time'], process_info['now'])
        self.assertLessEqual(0, process_info['pid'])
        # rules part (independent from state)
        self.assertIs(self.logger, process.rules.logger)
        self.assertListEqual(['*'], process.rules.addresses)
        #self.assertEqual(0, process.start_sequence)
        self.assertEqual(-1, process.rules.sequence)
        self.assertFalse(process.rules.required)
        self.assertFalse(process.rules.wait_exit)
        self.assertEqual(1, process.rules.expected_loading)

    def test_dependency_rules(self):
        """ Test the dependencies in process rules. """
        from supervisors.process import ProcessStatus
        process = ProcessStatus('10.0.0.1', any_process_info(), self.logger)
        # first test with no dependency issue
        process.rules.addresses = ['10.0.0.1', '10.0.0.2']
        process.rules.sequence = 1
        process.rules.required = True
        process.rules.wait_exit = False
        process.rules.expected_loading = 15
        # check dependencies
        process.rules.check_dependencies()
        # test that there is no difference
        self.assertListEqual(['10.0.0.1', '10.0.0.2'], process.rules.addresses)
        self.assertEqual(1, process.rules.sequence)
        self.assertTrue(process.rules.required)
        self.assertFalse(process.rules.wait_exit)
        self.assertEqual(15, process.rules.expected_loading)
        # second test with no dependency issue
        process.rules.addresses = ['10.0.0.2']
        process.rules.sequence = -1
        process.rules.required = False
        process.rules.wait_exit = True
        process.rules.expected_loading = 50
        # check dependencies
        process.rules.check_dependencies()
        # test that there is no difference
        self.assertListEqual(['10.0.0.2'], process.rules.addresses)
        self.assertEqual(-1, process.rules.sequence)
        self.assertFalse(process.rules.required)
        self.assertTrue(process.rules.wait_exit)
        self.assertEqual(50, process.rules.expected_loading)
        # test with required and no sequence
        process.rules.addresses = ['10.0.0.1']
        process.rules.sequence = -1
        process.rules.required = True
        process.rules.wait_exit = False
        process.rules.expected_loading = 5
        # check dependencies
        process.rules.check_dependencies()
        # test that process is not required anymore
        self.assertListEqual(['10.0.0.1'], process.rules.addresses)
        self.assertEqual(-1, process.rules.sequence)
        self.assertFalse(process.rules.required)
        self.assertFalse(process.rules.wait_exit)
        self.assertEqual(5, process.rules.expected_loading)
        # test empty addresses
        process.rules.addresses = []
        process.rules.sequence = -1
        process.rules.required = False
        process.rules.wait_exit = False
        process.rules.expected_loading = 0
        # check dependencies
        process.rules.check_dependencies()
        # test that all addresses are applicable
        self.assertListEqual(['*'], process.rules.addresses)
        self.assertEqual(-1, process.rules.sequence)
        self.assertFalse(process.rules.required)
        self.assertFalse(process.rules.wait_exit)
        self.assertEqual(0, process.rules.expected_loading)


    def test_namespec(self):
        """ Test of the process namspec. """
        from supervisors.process import ProcessStatus
        # test namespec when group and name are different
        info = process_info_by_name('segv')
        process = ProcessStatus('10.0.0.1', info, self.logger)
        self.assertEqual('crash:segv', process.namespec())
        # test namespec when group and name are identical
        info = process_info_by_name('firefox')
        process = ProcessStatus('10.0.0.1', info, self.logger)
        self.assertEqual('firefox', process.namespec())

    def test_stopped_running(self):
        """ Test the stopped / running status. """
        from supervisor.process import ProcessStates
        from supervisors.process import ProcessStatus
        # test with STOPPED process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.logger)
        self.assertTrue(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        # test with BACKOFF process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.BACKOFF), self.logger)
        self.assertFalse(process.stopped())
        self.assertTrue(process.running())
        self.assertTrue(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with RUNNING process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.RUNNING), self.logger)
        self.assertFalse(process.stopped())
        self.assertTrue(process.running())
        self.assertTrue(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertTrue(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with STOPPING process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPING), self.logger)
        self.assertFalse(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))

    def test_conflicting(self):
        """ Test the process conflicting rules. """
        from supervisor.process import ProcessStates
        from supervisors.process import ProcessStatus
        # when there is only one STOPPED process info, there is no conflict
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.logger)
        self.assertFalse(process.conflicting())
        # the addition of one RUNNING process info does not raise any conflict
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.RUNNING))
        self.assertFalse(process.conflicting())
        # the addition of one STOPPED process info does not raise any conflict
        process.add_info('10.0.0.3', any_process_info_by_state(ProcessStates.STOPPED))
        self.assertFalse(process.conflicting())
        # the addition of one STARTING process raises a conflict
        process.add_info('10.0.0.4', any_process_info_by_state(ProcessStates.STARTING))
        self.assertTrue(process.conflicting())
        # the replacement of the RUNNING process info by a STOPPED process info solves the conflict
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
        self.assertFalse(process.conflicting())
        # the replacement of one STOPPED process info by a RUNNING process info raises the conflict again
        process.add_info('10.0.0.1', any_process_info_by_state(ProcessStates.RUNNING))
        self.assertTrue(process.conflicting())

    def test_serialization(self):
        """ Test . """

    def test_add_info(self):
        """ Test . """

    def test_update_info(self):
        """ Test . """

    def test_update_times(self):
        """ Test . """

    def test_update_single_times(self):
        """ Test . """

    def test_invalidate_address(self):
        """ Test . """

    def test_update_status(self):
        """ Test . """

    def test_evaluate_conflict(self):
        """ Test . """

    def test_filter(self):
        """ Test . """

    def test_running_state(self):
        """ Test . """


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

