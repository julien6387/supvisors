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

import random
import sys
import unittest

from supvisors.tests.base import (MockedSupvisors, database_copy,
                                  any_process_info, any_stopped_process_info, any_running_process_info)


class ApplicationRulesTest(unittest.TestCase):
    """ Test case for the ApplicationRules class of the application module. """

    def test_create(self):
        """ Test the values set at construction. """
        from supvisors.application import ApplicationRules
        from supvisors.ttypes import StartingFailureStrategies, RunningFailureStrategies
        rules = ApplicationRules()
        # check application default rules
        self.assertEqual(0, rules.start_sequence)
        self.assertEqual(0, rules.stop_sequence)
        self.assertEqual(StartingFailureStrategies.ABORT, rules.starting_failure_strategy)
        self.assertEqual(RunningFailureStrategies.CONTINUE, rules.running_failure_strategy)

    def test_str(self):
        """ Test the string output. """
        from supvisors.application import ApplicationRules
        rules = ApplicationRules()
        self.assertEqual(
            'start_sequence=0 stop_sequence=0 starting_failure_strategy=ABORT running_failure_strategy=CONTINUE',
            str(rules))

    def test_serial(self):
        """ Test the serialization of the ApplicationRules object. """
        from supvisors.application import ApplicationRules
        rules = ApplicationRules()
        self.assertDictEqual({'start_sequence': 0, 'stop_sequence': 0,
                              'starting_failure_strategy': 'ABORT',
                              'running_failure_strategy': 'CONTINUE'}, rules.serial())


class ApplicationStatusTest(unittest.TestCase):
    """ Test case for the ApplicationStatus class of the application module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()

    def test_create(self):
        """ Test the values set at construction. """
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import ApplicationStates, StartingFailureStrategies, RunningFailureStrategies
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        # check application default attributes
        self.assertEqual('ApplicationTest', application.application_name)
        self.assertEqual(ApplicationStates.STOPPED, application.state)
        self.assertFalse(application.major_failure)
        self.assertFalse(application.minor_failure)
        self.assertFalse(application.processes)
        self.assertFalse(application.start_sequence)
        self.assertFalse(application.stop_sequence)
        # check application default rules
        self.assertEqual(0, application.rules.start_sequence)
        self.assertEqual(0, application.rules.stop_sequence)
        self.assertEqual(StartingFailureStrategies.ABORT, application.rules.starting_failure_strategy)
        self.assertEqual(RunningFailureStrategies.CONTINUE, application.rules.running_failure_strategy)

    def test_running(self):
        """ Test the running method. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        self.assertFalse(application.running())
        # add a stopped process
        info = any_stopped_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        application.add_process(process)
        application.update_status()
        self.assertFalse(application.running())
        # add a running process
        info = any_running_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        application.add_process(process)
        application.update_status()
        self.assertTrue(application.running())

    def test_stopped(self):
        """ Test the stopped method. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        self.assertTrue(application.stopped())
        # add a stopped process
        info = any_stopped_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        application.add_process(process)
        application.update_status()
        self.assertTrue(application.stopped())
        # add a running process
        info = any_running_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        application.add_process(process)
        application.update_status()
        self.assertFalse(application.stopped())

    def test_serialization(self):
        """ Test the serial method used to get a serializable form of Application. """
        import pickle
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import ApplicationStates
        # create address status instance
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        application._state = ApplicationStates.RUNNING
        application.major_failure = False
        application.minor_failure = True
        # test to_json method
        serialized = application.serial()
        self.assertDictEqual(serialized, {'application_name': 'ApplicationTest',
                                          'statecode': 2, 'statename': 'RUNNING',
                                          'major_failure': False, 'minor_failure': True})
        # test that returned structure is serializable using pickle
        dumped = pickle.dumps(serialized)
        loaded = pickle.loads(dumped)
        self.assertDictEqual(serialized, loaded)

    def test_add_process(self):
        """ Test the add_process method. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        # add a process to the application
        info = any_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        application.add_process(process)
        # check that process is stored
        self.assertIn(process.process_name, application.processes.keys())
        self.assertIs(process, application.processes[process.process_name])

    def test_update_sequences(self):
        """ Test the sequencing of the update_sequences method. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        # add processes to the application
        for info in database_copy():
            process = ProcessStatus(info['group'], info['name'], self.supvisors)
            process.add_info('10.0.0.1', info)
            # set random sequence to process
            process.rules.start_sequence = random.randint(0, 2)
            process.rules.stop_sequence = random.randint(0, 2)
            application.add_process(process)
        # call the sequencer
        application.update_sequences()
        # check the sequencing of the starting
        sequences = sorted({process.rules.start_sequence for process in application.processes.values()})
        # as key is an integer, the sequence dictionary should be sorted but pypy doesn't...
        for sequence, processes in sorted(application.start_sequence.items()):
            self.assertEqual(sequence, sequences.pop(0))
            self.assertListEqual(sorted(processes, key=lambda x: x.process_name),
                                 sorted([proc for proc in application.processes.values() if
                                         sequence == proc.rules.start_sequence], key=lambda x: x.process_name))
        # check the sequencing of the stopping
        sequences = sorted({process.rules.stop_sequence for process in application.processes.values()})
        # as key is an integer, the sequence dictionary should be sorted but pypy doesn't...
        for sequence, processes in sorted(application.stop_sequence.items()):
            self.assertEqual(sequence, sequences.pop(0))
            self.assertListEqual(sorted(processes, key=lambda x: x.process_name),
                                 sorted([proc for proc in application.processes.values() if
                                         sequence == proc.rules.stop_sequence], key=lambda x: x.process_name))

    def test_update_status(self):
        """ Test the rules to update the status of the application method. """
        from supervisor.states import ProcessStates
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        from supvisors.ttypes import ApplicationStates
        application = ApplicationStatus('ApplicationTest', self.supvisors.logger)
        # add processes to the application
        for info in database_copy():
            process = ProcessStatus(info['group'], info['name'], self.supvisors)
            process.add_info('10.0.0.1', info)
            application.add_process(process)
        # init status
        # there are lots of states but the 'strongest' is STARTING
        # STARTING is a 'running' state so major/minor failures are applicable
        application.update_status()
        self.assertEqual(ApplicationStates.STARTING, application.state)
        # there is a FATAL state in the process database
        # no rule is set for processes, so there are only minor failures
        self.assertFalse(application.major_failure)
        self.assertTrue(application.minor_failure)
        # set FATAL process to major
        fatal_process = next(
            (process for process in application.processes.values() if process.state == ProcessStates.FATAL), None)
        fatal_process.rules.required = True
        # update status. major failure is now expected
        application.update_status()
        self.assertEqual(ApplicationStates.STARTING, application.state)
        self.assertTrue(application.major_failure)
        self.assertFalse(application.minor_failure)
        # set STARTING process to RUNNING
        starting_process = next(
            (process for process in application.processes.values() if process.state == ProcessStates.STARTING), None)
        starting_process.state = ProcessStates.RUNNING
        # update status. there is still one BACKOFF process leading to STARTING application
        application.update_status()
        self.assertEqual(ApplicationStates.STARTING, application.state)
        self.assertTrue(application.major_failure)
        self.assertFalse(application.minor_failure)
        # set BACKOFF process to EXITED
        backoff_process = next(
            (process for process in application.processes.values() if process.state == ProcessStates.BACKOFF), None)
        backoff_process.state = ProcessStates.EXITED
        # update status. the 'strongest' state is now STOPPING
        # as STOPPING is not a 'running' state, failures are not applicable
        application.update_status()
        self.assertEqual(ApplicationStates.STOPPING, application.state)
        self.assertFalse(application.major_failure)
        self.assertFalse(application.minor_failure)
        # set STOPPING process to STOPPED
        stopping_process = next(
            (process for process in application.processes.values() if process.state == ProcessStates.STOPPING), None)
        stopping_process.state = ProcessStates.STOPPED
        # update status. the 'strongest' state is now RUNNING
        # failures are applicable again
        application.update_status()
        self.assertEqual(ApplicationStates.RUNNING, application.state)
        self.assertTrue(application.major_failure)
        self.assertFalse(application.minor_failure)
        # set RUNNING processes to STOPPED
        for process in application.processes.values():
            if process.state == ProcessStates.RUNNING:
                process.state = ProcessStates.STOPPED
        # update status. the 'strongest' state is now RUNNING
        # failures are not applicable anymore
        application.update_status()
        self.assertEqual(ApplicationStates.STOPPED, application.state)
        self.assertFalse(application.major_failure)
        self.assertFalse(application.minor_failure)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
