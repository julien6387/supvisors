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
import time
import unittest

from mock import call, patch, Mock

from supvisors.tests.base import MockedSupvisors, database_copy


class CommanderTest(unittest.TestCase):
    """ Test case for the Commander class of the commander module. """

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        from supvisors.process import ProcessStatus
        self.supvisors = MockedSupvisors()
        # store lists for tests
        self.process_list_1 = [ProcessStatus('appli_A', 'dummy_A1', self.supvisors),
            ProcessStatus('appli_A', 'dummy_A2', self.supvisors),
            ProcessStatus('appli_A', 'dummy_A3', self.supvisors)]
        self.process_list_2 = [ProcessStatus('appli_B', 'dummy_B1', self.supvisors)]

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        self.assertIs(self.supvisors, commander.supvisors)
        self.assertIs(self.supvisors.logger, commander.logger)
        self.assertDictEqual({}, commander.planned_sequence)
        self.assertDictEqual({}, commander.planned_jobs)
        self.assertDictEqual({}, commander.current_jobs)

    def test_in_progress(self):
        """ Test the in_progress method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        self.assertFalse(commander.in_progress())
        commander.planned_sequence = {0: {'if': {0: self.process_list_1}}}
        self.assertTrue(commander.in_progress())
        commander.planned_jobs = {'then': {1: self.process_list_2}}
        self.assertTrue(commander.in_progress())
        commander.current_jobs = {'else': []}
        self.assertTrue(commander.in_progress())
        commander.planned_sequence = {}
        self.assertTrue(commander.in_progress())
        commander.planned_jobs = {}
        self.assertTrue(commander.in_progress())
        commander.current_jobs = {}
        self.assertFalse(commander.in_progress())

    def test_has_application(self):
        """ Test the has_application method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        self.assertFalse(commander.has_application('if'))
        self.assertFalse(commander.has_application('then'))
        self.assertFalse(commander.has_application('else'))
        commander.planned_sequence = {0: {'if': {0: self.process_list_1}}}
        self.assertTrue(commander.has_application('if'))
        self.assertFalse(commander.has_application('then'))
        commander.planned_jobs = {'then': {1: self.process_list_2}}
        self.assertTrue(commander.has_application('if'))
        self.assertTrue(commander.has_application('then'))
        self.assertFalse(commander.has_application('else'))
        commander.current_jobs = {'else': []}
        self.assertTrue(commander.has_application('if'))
        self.assertTrue(commander.has_application('then'))
        self.assertTrue(commander.has_application('else'))
        commander.planned_sequence = {}
        self.assertFalse(commander.has_application('if'))
        self.assertTrue(commander.has_application('then'))
        self.assertTrue(commander.has_application('else'))
        commander.planned_jobs = {}
        self.assertFalse(commander.has_application('if'))
        self.assertFalse(commander.has_application('then'))
        self.assertTrue(commander.has_application('else'))
        commander.current_jobs = {}
        self.assertFalse(commander.has_application('if'))
        self.assertFalse(commander.has_application('then'))
        self.assertFalse(commander.has_application('else'))

    def test_printable_process_list(self):
        """ Test the printable_process_list method. """
        from supvisors.commander import Commander
        # test with empty list
        printable = Commander.printable_process_list([])
        self.assertListEqual([], printable)
        # test with list having a single element
        printable = Commander.printable_process_list(self.process_list_2)
        self.assertListEqual(['appli_B:dummy_B1'], printable)
        # test with list having multiple elements
        printable = Commander.printable_process_list(self.process_list_1)
        self.assertListEqual(['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'], printable)

    def test_printable_current_jobs(self):
        """ Test the printable_current_jobs method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        # test with empty structure
        commander.current_jobs = {}
        printable = commander.printable_current_jobs()
        self.assertDictEqual({}, printable)
        # test with complex structure
        commander.current_jobs = {'if': [], 'then': self.process_list_1, 'else': self.process_list_2}
        printable = commander.printable_current_jobs()
        self.assertDictEqual({'if': [], 'then': ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'],
            'else': ['appli_B:dummy_B1']}, printable)

    def test_printable_planned_jobs(self):
        """ Test the printable_planned_jobs method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        # test with empty structure
        commander.planned_jobs = {}
        printable = commander.printable_planned_jobs()
        self.assertDictEqual({}, printable)
        # test with complex structure
        commander.planned_jobs = {'if': {0: self.process_list_1, 1:[]}, 'then': {2: self.process_list_2}, 'else': {}}
        printable = commander.printable_planned_jobs()
        self.assertDictEqual({'if': {0: ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'], 1:[]},
            'then': {2: ['appli_B:dummy_B1']}, 'else': {}}, printable)

    def test_printable_planned_sequence(self):
        """ Test the printable_planned_sequence method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        # test with empty structure
        commander.planned_sequence = {}
        printable = commander.printable_planned_sequence()
        self.assertDictEqual({}, printable)
        # test with complex structure
        commander.planned_sequence = {0: {'if': {-1: [], 0: self.process_list_1},
            'then': {2: self.process_list_2}}, 3: {'else': {}}}
        printable = commander.printable_planned_sequence()
        self.assertDictEqual({0: {'if': {-1: [], 0: ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3']},
            'then': {2: ['appli_B:dummy_B1']}}, 3: {'else': {}}}, printable)

    def test_process_application_jobs(self):
        """ Test the process_application_jobs method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        # fill planned_jobs
        commander.planned_jobs = {'if': {0: self.process_list_1, 1:[]}, 'then': {2: self.process_list_2}, 'else': {}}
        # define patch function
        def fill_jobs(*args, **kwargs):
            args[1].append(args[0])
        with patch.object(commander, 'process_job', side_effect=fill_jobs) as mocked_job:
            # test with unknown application
            commander.process_application_jobs('while')
            self.assertDictEqual({}, commander.current_jobs)
            self.assertDictEqual({'if': {0: self.process_list_1, 1:[]}, 'then': {2: self.process_list_2}, 'else': {}},
                commander.planned_jobs)
            self.assertEqual(0, mocked_job.call_count)
            # test with known application: sequence 0 of 'if' application is popped
            commander.process_application_jobs('if')
            self.assertDictEqual({'if': {1:[]}, 'then': {2: self.process_list_2}, 'else': {}}, commander.planned_jobs)
            self.assertDictEqual({'if': self.process_list_1}, commander.current_jobs)
            self.assertEqual(3, mocked_job.call_count)
            # test with known application: sequence 1 of 'if' application is popped
            mocked_job.reset_mock()
            commander.process_application_jobs('if')
            self.assertDictEqual({'then': {2: self.process_list_2}, 'else': {}}, commander.planned_jobs)
            self.assertDictEqual({}, commander.current_jobs)
            self.assertEqual(0, mocked_job.call_count)
        # test that process_job method must be implemented
        with self.assertRaises(NotImplementedError):
            commander.process_application_jobs('then')
        self.assertDictEqual({'then': {}, 'else': {}}, commander.planned_jobs)
        self.assertDictEqual({'then': []}, commander.current_jobs)

    def test_initial_jobs(self):
        """ Test the initial_jobs method. """
        from supvisors.commander import Commander
        commander = Commander(self.supvisors)
        # test with empty structure
        commander.planned_sequence = {}
        commander.initial_jobs()
        self.assertDictEqual({}, commander.planned_jobs)
        # test with complex structure
        commander.planned_sequence = {0: {'if': {2: [], 0: self.process_list_1},
            'then': {2: self.process_list_2}}, 3: {'else': {}}}
        # define patch function
        def fill_jobs(*args, **kwargs):
            args[1].append(args[0])
        with patch.object(commander, 'process_job', side_effect=fill_jobs) as mocked_job:
            commander.initial_jobs()
            # test impact on internal attributes
            self.assertDictEqual({3: {'else': {}}}, commander.planned_sequence)
            self.assertDictEqual({'if': {2: []}}, commander.planned_jobs)
            self.assertDictEqual({'if': self.process_list_1, 'then': self.process_list_2}, commander.current_jobs)
            self.assertEqual(4, mocked_job.call_count)


class StarterTest(unittest.TestCase):
    """ Test case for the Starter class of the commander module. """

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        from supvisors.process import ProcessStatus
        self.supvisors = MockedSupvisors()
        # store list for tests
        self.process_list = []
        for info in database_copy():
            proc_status = ProcessStatus(info['group'], info['name'], self.supvisors)
            proc_status.add_info('10.0.0.1', info)
            self.process_list.append(proc_status)

    def _get_test_process(self, process_name):
        """ Return the process in databse corresponding to process_name. """
        return next(process for process in self.process_list if process.process_name == process_name)

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.commander import Commander, Starter
        from supvisors.ttypes import StartingStrategies
        starter = Starter(self.supvisors)
        self.assertIsInstance(starter, Commander)
        self.assertEqual(StartingStrategies.CONFIG, starter._strategy)
        starter.strategy = StartingStrategies.LESS_LOADED
        self.assertEqual(StartingStrategies.LESS_LOADED, starter.strategy)

    def test_abort(self):
        """ Test the abort method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # fill attributes
        starter.planned_sequence = {3: {'else': {}}}
        starter.planned_jobs = {'if': {2: []}}
        starter.current_jobs = {'if': ['dummy_1', 'dummy_2'], 'then': ['dummy_3']}
        # call abort and check attributes
        starter.abort()
        self.assertDictEqual({}, starter.planned_sequence)
        self.assertDictEqual({}, starter.planned_jobs)
        self.assertDictEqual({}, starter.current_jobs)

    def test_store_application_start_sequence(self):
        """ Test the store_application_start_sequence method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # create 2 application start_sequences
        application1 = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for process in self.process_list:
            if process.application_name == 'sample_test_1':
                application1.start_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        application2 = ApplicationStatus('sample_test_2', self.supvisors.logger)
        for process in self.process_list:
            if process.application_name == 'sample_test_2':
                application2.start_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        # call method ans check result
        starter.store_application_start_sequence(application1)
        # check that application sequence 0 is not in starter planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'], 2: ['sample_test_1:xclock']}}},
            starter.printable_planned_sequence())
        # call method a second time and check result
        starter.store_application_start_sequence(application2)
        # check that application sequence 0 is not in starter planned sequence
        self.assertDictEqual({0: {'sample_test_1': {
                1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                2: ['sample_test_1:xclock']},
            'sample_test_2': {1: ['sample_test_2:sleep']}}},
            starter.printable_planned_sequence())

    def test_process_failure_optional(self):
        """ Test the process_failure method with an optional process. """
        from supvisors.commander import Starter
        # create the instance
        starter = Starter(self.supvisors)
        # prepare context
        process = Mock()
        process.rules = Mock(required=False)
        test_planned_jobs = {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
        # get the patch for stopper / stop_application
        mocked_stopper = self.supvisors.stopper.stop_application
        # test with a process not required
        starter.planned_jobs = test_planned_jobs.copy()
        starter.process_failure(process)
        # test planned_jobs is unchanged
        self.assertDictEqual(test_planned_jobs, starter.planned_jobs)
        # test stop_application is not called
        self.assertEqual(0, mocked_stopper.call_count)

    def test_process_failure_required(self):
        """ Test the process_failure method with a required process. """
        from supvisors.commander import Starter
        from supvisors.ttypes import StartingFailureStrategies
        # create the instance
        starter = Starter(self.supvisors)
        # prepare context
        process = Mock(application_name='appli_1')
        process.rules = Mock(required=True)
        application = Mock()
        self.supvisors.context.applications = {'appli_1': application, 'proc_2': None}
        test_planned_jobs = {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
        # get the patch for stopper / stop_application
        mocked_stopper = self.supvisors.stopper.stop_application
        # test ABORT starting strategy
        starter.planned_jobs = test_planned_jobs.copy()
        application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.ABORT)
        starter.process_failure(process)
        # check that application has been removed from planned jobs and stopper wasn't called
        self.assertDictEqual({'appli_2': {1: ['proc_2']}}, starter.planned_jobs)
        self.assertEqual(0, mocked_stopper.call_count)
        # test CONTINUE starting strategy
        starter.planned_jobs = test_planned_jobs.copy()
        application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.CONTINUE)
        starter.process_failure(process)
        # check that application has NOT been removed from planned jobs and stopper wasn't called
        self.assertDictEqual({'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}},
            starter.planned_jobs)
        self.assertEqual(0, mocked_stopper.call_count)
        # test STOP starting strategy
        starter.planned_jobs = test_planned_jobs.copy()
        application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.STOP)
        starter.process_failure(process)
        # check that application has been removed from planned jobs and stopper has been called
        self.assertDictEqual({'appli_2': {1: ['proc_2']}}, starter.planned_jobs)
        self.assertEqual([call(application)], mocked_stopper.call_args_list)

    def test_force_process_fatal(self):
        """ Test the force_process_fatal method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # get patches
        mocked_listener = self.supvisors.listener.force_process_fatal
        mocked_source = self.supvisors.info_source.force_process_fatal
        # test with no info_source exception
        starter.force_process_fatal('proc', 'any reason')
        self.assertEqual([call('proc', 'any reason')], mocked_source.call_args_list)
        self.assertEqual(0, mocked_listener.call_count)
        mocked_source.reset_mock()
        # test with info_source exception
        mocked_source.side_effect = KeyError
        starter.force_process_fatal('proc', 'any reason')
        self.assertEqual([call('proc', 'any reason')], mocked_source.call_args_list)
        self.assertEqual([call('proc')], mocked_listener.call_args_list)

    def test_on_event(self):
        """ Test the on_event method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # apply patches
        with patch.object(starter, 'on_event_in_sequence') as mocked_in:
            with patch.object(starter, 'on_event_out_of_sequence') as mocked_out:
                # set test current_jobs
                for process in self.process_list:
                    starter.current_jobs.setdefault(process.application_name, []).append(process)
                self.assertIn('sample_test_1', starter.current_jobs)
                # test that on_event_out_of_sequence is called when process is not in current jobs
                # due to unknown application
                process = Mock(application_name='unknown_application')
                starter.on_event(process)
                self.assertEqual(0, mocked_in.call_count)
                self.assertEqual([(call(process))], mocked_out.call_args_list)
                mocked_out.reset_mock()
                # test that on_event_out_of_sequence is called when process is not in current jobs
                # due to unknown process
                process = Mock(application_name='sample_test_1')
                starter.on_event(process)
                self.assertEqual(0, mocked_in.call_count)
                self.assertEqual([(call(process))], mocked_out.call_args_list)
                mocked_out.reset_mock()
                # test that on_event_in_sequence is called when process is in list
                jobs = starter.current_jobs['sample_test_1']
                process = next(iter(jobs))
                starter.on_event(process)
                self.assertEqual(0, mocked_out.call_count)
                self.assertEqual([(call(process, jobs))], mocked_in.call_args_list)

    def test_on_event_in_sequence(self):
        """ Test the on_event_in_sequence method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Starter
        from supvisors.ttypes import StartingFailureStrategies
        starter = Starter(self.supvisors)
        # set test planned_jobs and current_jobs
        starter.planned_jobs = {'sample_test_1': {}}
        for process in self.process_list:
            starter.current_jobs.setdefault(process.application_name, []).append(process)
        # add application context
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        application.rules.starting_failure_strategy = StartingFailureStrategies.CONTINUE
        self.supvisors.context.applications['sample_test_1'] = application
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        application.rules.starting_failure_strategy = StartingFailureStrategies.ABORT
        self.supvisors.context.applications['sample_test_2'] = application
        # add patches to simplify test
        with patch.object(starter, 'process_application_jobs') as mocked_process_jobs:
            with patch.object(starter, 'initial_jobs') as mocked_init_jobs:
                # with sample_test_1 application
                # test STOPPED process
                process = self._get_test_process('xlogo')
                jobs = starter.current_jobs['sample_test_1']
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn(process, jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # test STOPPING process: xclock
                process = self._get_test_process('xclock')
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn(process, jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # test RUNNING process: xfontsel (last process of this application)
                process = self._get_test_process('xfontsel')
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn('sample_test_1', starter.current_jobs)
                self.assertEqual(1, mocked_process_jobs.call_count)
                self.assertEqual(call('sample_test_1'), mocked_process_jobs.call_args)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # reset resources
                mocked_process_jobs.reset_mock()
                # with sample_test_2 application
                # test RUNNING process: yeux_01
                process = self._get_test_process('yeux_01')
                jobs = starter.current_jobs['sample_test_2']
                process.rules.wait_exit = True
                process.ignore_wait_exit = True
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn(process, jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # test EXITED / expected process: yeux_00
                process = self._get_test_process('yeux_00')
                process.rules.wait_exit = True
                process.expected_exit = True
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn(process, jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # test FATAL process: sleep (last process of this application)
                process = self._get_test_process('sleep')
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn('sample_test_2', starter.current_jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # with crash application
                # test STARTING process: late_segv
                process = self._get_test_process('late_segv')
                jobs = starter.current_jobs['crash']
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertIn(process, jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # test BACKOFF process: segv (last process of this application)
                process = self._get_test_process('segv')
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertIn(process, jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(0, mocked_init_jobs.call_count)
                # with firefox application
                # empty planned_jobs to trigger another behaviour
                starter.planned_jobs = {}
                # test EXITED / unexpected process: firefox
                process = self._get_test_process('firefox')
                jobs = starter.current_jobs['firefox']
                process.rules.wait_exit = True
                process.expected_exit = False
                self.assertIn(process, jobs)
                starter.on_event_in_sequence(process, jobs)
                self.assertFalse(process.ignore_wait_exit)
                self.assertNotIn('firefox', starter.current_jobs)
                self.assertEqual(0, mocked_process_jobs.call_count)
                self.assertEqual(1, mocked_init_jobs.call_count)

    def test_on_event_out_of_sequence(self):
        """ Test how failure are raised in on_event_out_of_sequence method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # set test planned_jobs and current_jobs
        starter.planned_jobs = {'sample_test_2': {1: []}}
        for process in self.process_list:
            starter.current_jobs.setdefault(process.application_name, []).append(process)
        # apply patch
        with patch.object(starter, 'process_failure') as mocked_failure:
            # test that process_failure is not called if process is not crashed
            process = next(proc for proc in self.process_list if not proc.crashed())
            starter.on_event_out_of_sequence(process)
            self.assertEqual(0, mocked_failure.call_count)
            # test that process_failure is not called if process is not in planned jobs
            process = next(proc for proc in self.process_list
                if proc.application_name == 'sample_test_1')
            starter.on_event_out_of_sequence(process)
            self.assertEqual(0, mocked_failure.call_count)
            # get a process crashed and in planned jobs
            process = next(proc for proc in self.process_list
                if proc.crashed() and proc.application_name == 'sample_test_2')
            # test that process_failure is called if process' starting is not planned
            starter.on_event_out_of_sequence(process)
            self.assertEqual([(call(process))], mocked_failure.call_args_list)
            mocked_failure.reset_mock()
            # test that process_failure is not called if process' starting is still planned
            starter.planned_jobs = {'sample_test_2': {1: [process]}}
            starter.on_event_out_of_sequence(process)
            self.assertEqual(0, mocked_failure.call_count)

    def test_check_starting(self):
        """ Test the check_starting method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # test with no jobs
        completed = starter.check_starting()
        self.assertTrue(completed)
        # set test current_jobs
        # xfontsel is RUNNING, xlogo is STOPPED, yeux_00 is EXITED, yeux_01 is RUNNING
        starter.current_jobs = {'sample_test_1': [self._get_test_process('xfontsel'), self._get_test_process('xlogo')],
            'sample_test_2': [self._get_test_process('yeux_00'), self._get_test_process('yeux_01')]}
        # assign request_time to processes in current_jobs
        for process_list in starter.current_jobs.values():
            for process in process_list:
                process.request_time = time.time()
        # stopped processes have a recent request time: nothing done
        with patch.object(starter, 'force_process_fatal') as mocked_force:
            completed = starter.check_starting()
            self.assertFalse(completed)
            self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                'sample_test_2': ['sample_test_2:yeux_00', 'sample_test_2:yeux_01']}, starter.printable_current_jobs())
            self.assertEqual(0, mocked_force.call_count)
        # re-assign last_event_time and request_time to processes in current_jobs
        for process_list in starter.current_jobs.values():
            for process in process_list:
                process.last_event_time = 0
                process.request_time = 0
        # stopped processes have an old request time: process_failure called
        with patch.object(starter, 'force_process_fatal') as mocked_force:
            completed = starter.check_starting()
            self.assertFalse(completed)
            self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                'sample_test_2': ['sample_test_2:yeux_00', 'sample_test_2:yeux_01']}, starter.printable_current_jobs())
            str_error = 'Still stopped 5 seconds after start request'
            self.assertItemsEqual([call('sample_test_1:xlogo', str_error), 
                call('sample_test_2:yeux_00', str_error)], mocked_force.call_args_list)

    @patch('supvisors.commander.Starter.force_process_fatal')
    def test_process_job(self, mocked_force):
        """ Test the process_job method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # get patches
        mocked_pusher = self.supvisors.zmq.pusher.send_start_process
        # test with a possible starting address
        with patch('supvisors.commander.get_address', return_value='10.0.0.1') as mocked_address:
            # test with running process
            process = self._get_test_process('xfontsel')
            process.ignore_wait_exit = True
            jobs = []
            # call the process_jobs
            starter.process_job(process, jobs)
            # process cannot be started, reset its config
            self.assertFalse(process.ignore_wait_exit)
            # starting methods are not called
            self.assertListEqual([], jobs)
            self.assertEqual(0, mocked_address.call_count)
            self.assertEqual(0, mocked_pusher.call_count)
            # failure method is not called
            self.assertEqual(0, mocked_force.call_count)
            # test with stopped process
            process = self._get_test_process('xlogo')
            process.ignore_wait_exit = True
            jobs = []
            # call the process_jobs
            starter.process_job(process, jobs)
            # process can be started, config unchanged
            self.assertTrue(process.ignore_wait_exit)
            # starting methods are called
            self.assertListEqual([process], jobs)
            self.assertEqual(1, mocked_address.call_count)
            self.assertEqual(1, mocked_pusher.call_count)
            self.assertEqual(call('10.0.0.1', 'sample_test_1:xlogo', ''), mocked_pusher.call_args)
            mocked_pusher.reset_mock()
            # failure method is not called
            self.assertEqual(0, mocked_force.call_count)
        # test with no starting address
        with patch('supvisors.commander.get_address', return_value=None):
            # test with stopped process
            process = self._get_test_process('xlogo')
            process.ignore_wait_exit = True
            jobs = []
            # call the process_jobs
            starter.process_job(process, jobs)
            # process cannot be started, reset its config
            self.assertFalse(process.ignore_wait_exit)
            # starting methods are not called
            self.assertListEqual([], jobs)
            self.assertEqual(0, mocked_pusher.call_count)
            # failure method is called
            self.assertEqual([call('sample_test_1:xlogo', 'no resource available')],
                mocked_force.call_args_list)

    def test_start_process(self):
        """ Test the start_process method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        # get any process
        xlogo_process = self._get_test_process('xlogo')
        # test failure
        with patch.object(starter, 'process_job') as mocked_jobs:
            start_result = starter.start_process('strategy', xlogo_process, 'extra_args')
            self.assertEqual('strategy', starter.strategy)
            self.assertEqual('extra_args', xlogo_process.extra_args)
            self.assertTrue(xlogo_process.ignore_wait_exit)
            self.assertDictEqual({}, starter.current_jobs)
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertTrue(start_result)
        # test success
        def success_job(*args, **kwargs):
            args[1].append(args[0])
        with patch.object(starter, 'process_job', side_effect=success_job) as mocked_jobs:
            start_result = starter.start_process('strategy', xlogo_process, 'extra_args')
            self.assertEqual('strategy', starter.strategy)
            self.assertEqual('extra_args', xlogo_process.extra_args)
            self.assertTrue(xlogo_process.ignore_wait_exit)
            self.assertDictEqual({'sample_test_1': [xlogo_process]}, starter.current_jobs)
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertFalse(start_result)
            # get any other process
            yeux_process = self._get_test_process('yeux_00')
            # test that success complements current_jobs
            start_result = starter.start_process(3, yeux_process)
            self.assertEqual(3, starter.strategy)
            self.assertEqual('', yeux_process.extra_args)
            self.assertTrue(yeux_process.ignore_wait_exit)
            self.assertDictEqual({'sample_test_1': [xlogo_process], 'sample_test_2': [yeux_process]},
                starter.current_jobs)
            self.assertEqual(2, mocked_jobs.call_count)
            self.assertFalse(start_result)

    def test_default_start_process(self):
        """ Test the default_start_process method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        with patch.object(starter, 'start_process', return_value=True) as mocked_start:
            # test that default_start_process just calls start_process
            # with the default strategy
            process = Mock()
            result = starter.default_start_process(process)
            self.assertTrue(result)
            self.assertEqual([call(self.supvisors.options.starting_strategy,
                process)], mocked_start.call_args_list)

    def test_start_application(self):
        """ Test the start_application method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Starter
        from supvisors.ttypes import ApplicationStates
        starter = Starter(self.supvisors)
        # create application start_sequence
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for process in self.process_list:
            if process.application_name == 'sample_test_1':
                application.start_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        # patch the starter.process_application_jobs
        def success_job(*args, **kwargs):
            args[1].append(args[0])
        with patch.object(starter, 'process_job', side_effect=success_job) as mocked_jobs:
            # test start_application on a running application
            application._state = ApplicationStates.RUNNING
            test_result = starter.start_application(1, application)
            self.assertTrue(test_result)
            self.assertEqual(1, starter.strategy)
            self.assertDictEqual({}, starter.planned_sequence)
            self.assertDictEqual({}, starter.planned_jobs)
            self.assertDictEqual({}, starter.current_jobs)
            self.assertEqual(0, mocked_jobs.call_count)
            # test start_application on a stopped application
            application._state = ApplicationStates.STOPPED
            test_result = starter.start_application(1, application)
            self.assertFalse(test_result)
            self.assertEqual(1, starter.strategy)
            # only planned jobs and not current jobs because of process_application_jobs patch
            self.assertDictEqual({}, starter.planned_sequence)
            self.assertDictEqual({'sample_test_1': {2: ['sample_test_1:xclock']}}, starter.printable_planned_jobs())
            self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo']}, starter.printable_current_jobs())
            self.assertEqual(2, mocked_jobs.call_count)

    def test_default_start_application(self):
        """ Test the default_start_application method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        with patch.object(starter, 'start_application', return_value=True) as mocked_start:
            # test that default_start_application just calls start_application
            # with the default strategy
            application = Mock()
            result = starter.default_start_application(application)
            self.assertTrue(result)
            self.assertEqual([call(self.supvisors.options.starting_strategy,
                application)], mocked_start.call_args_list)

    def test_start_applications(self):
        """ Test the start_applications method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Starter
        from supvisors.ttypes import ApplicationStates
        starter = Starter(self.supvisors)
        # create one running application
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        application._state = ApplicationStates.RUNNING
        self.supvisors.context.applications['sample_test_1'] = application
        # create one stopped application with a start_sequence > 0
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        application.rules.start_sequence = 2
        for process in self.process_list:
            if process.application_name == 'sample_test_2':
                application.start_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        self.supvisors.context.applications['sample_test_2'] = application
        # create one stopped application with a start_sequence == 0
        application = ApplicationStatus('crash', self.supvisors.logger)
        application.rules.start_sequence = 0
        self.supvisors.context.applications['crash'] = application
        # call starter start_applications and check that only sample_test_2 is triggered
        with patch.object(starter, 'process_application_jobs') as mocked_jobs:
            starter.start_applications()
            self.assertDictEqual({}, starter.planned_sequence)
            self.assertDictEqual({'sample_test_2': {1: ['sample_test_2:sleep']}}, starter.printable_planned_jobs())
            # current jobs is empty because of process_application_jobs mocking
            self.assertDictEqual({}, starter.printable_current_jobs())
            self.assertEqual(0, starter.strategy)
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertEqual(call('sample_test_2'), mocked_jobs.call_args)


class StopperTest(unittest.TestCase):
    """ Test case for the Stopper class of the commander module. """

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        from supvisors.process import ProcessStatus
        self.supvisors = MockedSupvisors()
        # store list for tests
        self.process_list = []
        for info in database_copy():
            proc_status = ProcessStatus(info['group'], info['name'], self.supvisors)
            proc_status.add_info('10.0.0.1', info)
            self.process_list.append(proc_status)

    def _get_test_process(self, process_name):
        """ Return the first process corresponding to process_name. """
        return next(process for process in self.process_list
            if process.process_name == process_name)

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.commander import Commander, Stopper
        stopper = Stopper(self.supvisors)
        self.assertIsInstance(stopper, Commander)

    @patch('supvisors.commander.Stopper.force_process_unknown')
    def test_check_stopping(self, mocked_force):
        """ Test the check_stopping method. """
        from supvisors.commander import Stopper
        stopper = Stopper(self.supvisors)
        # test with no jobs
        completed = stopper.check_stopping()
        self.assertTrue(completed)
        # set test current_jobs
        # xfontsel is RUNNING, xlogo is STOPPED, yeux_00 is EXITED, yeux_01 is RUNNING
        stopper.current_jobs = {'sample_test_1': [self._get_test_process('xfontsel'), self._get_test_process('xlogo')],
            'sample_test_2': [self._get_test_process('yeux_00'), self._get_test_process('yeux_01')]}
        # assign request_time to processes in current_jobs
        for process_list in stopper.current_jobs.values():
            for process in process_list:
                process.request_time = time.time()
        # processes have a recent request time: nothing done
        completed = stopper.check_stopping()
        self.assertFalse(completed)
        self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
            'sample_test_2': ['sample_test_2:yeux_00', 'sample_test_2:yeux_01']}, stopper.printable_current_jobs())
        self.assertEqual(0, mocked_force.call_count)
        # re-assign request_time to processes in current_jobs
        for process_list in stopper.current_jobs.values():
            for process in process_list:
                process.last_event_time = 0
                process.request_time = 0
        # processes have an old request time: process_failure called
        completed = stopper.check_stopping()
        self.assertFalse(completed)
        self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
            'sample_test_2': ['sample_test_2:yeux_00', 'sample_test_2:yeux_01']}, stopper.printable_current_jobs())
        str_error = 'Still running 5 seconds after stop request'
        self.assertItemsEqual([call('sample_test_1:xfontsel', str_error), 
            call('sample_test_2:yeux_01', str_error)], mocked_force.call_args_list)

    @patch('supvisors.commander.Stopper.process_application_jobs')
    @patch('supvisors.commander.Stopper.initial_jobs')
    def test_on_event(self, mocked_init, mocked_process):
        """ Test the on_event method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Stopper
        from supvisors.process import ProcessStatus
        from supvisors.ttypes import ProcessStates
        stopper = Stopper(self.supvisors)
        # set test planned_jobs and current_jobs
        stopper.planned_jobs = {'sample_test_2': {}}
        for process in self.process_list:
            stopper.current_jobs.setdefault(process.application_name, []).append(process)
        # add application context
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_1'] = application
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_2'] = application
        # try with unknown process
        process = ProcessStatus('dummy_application', 'dummy_process', self.supvisors)
        stopper.on_event(process)
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # with sample_test_1 application
        # test STOPPED process
        process = self._get_test_process('xlogo')
        self.assertIn(process, stopper.current_jobs['sample_test_1'])
        stopper.on_event(process)
        self.assertNotIn(process, stopper.current_jobs['sample_test_1'])
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # test STOPPING process: xclock
        process = self._get_test_process('xclock')
        self.assertIn(process, stopper.current_jobs['sample_test_1'])
        stopper.on_event(process)
        self.assertIn(process, stopper.current_jobs['sample_test_1'])
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # test RUNNING process: xfontsel
        process = self._get_test_process('xfontsel')
        self.assertIn(process, stopper.current_jobs['sample_test_1'])
        stopper.on_event(process)
        self.assertIn('sample_test_1', stopper.current_jobs.keys())
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # with sample_test_2 application
        # test EXITED / expected process: yeux_00
        process = self._get_test_process('yeux_00')
        self.assertIn(process, stopper.current_jobs['sample_test_2'])
        stopper.on_event(process)
        self.assertNotIn(process, stopper.current_jobs['sample_test_2'])
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # test FATAL process: sleep
        process = self._get_test_process('sleep')
        self.assertIn(process, stopper.current_jobs['sample_test_2'])
        stopper.on_event(process)
        self.assertIn('sample_test_2', stopper.current_jobs.keys())
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # test RUNNING process: yeux_01
        process = self._get_test_process('yeux_01')
        self.assertIn(process, stopper.current_jobs['sample_test_2'])
        stopper.on_event(process)
        self.assertIn(process, stopper.current_jobs['sample_test_2'])
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # force yeux_01 state and re-test
        process._state = ProcessStates.STOPPED
        self.assertIn(process, stopper.current_jobs['sample_test_2'])
        stopper.on_event(process)
        self.assertNotIn('sample_test_2', stopper.current_jobs.keys())
        self.assertEqual(1, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # reset resources
        mocked_process.reset_mock()
        # with crash application
        # test STARTING process: late_segv
        process = self._get_test_process('late_segv')
        self.assertIn(process, stopper.current_jobs['crash'])
        stopper.on_event(process)
        self.assertIn(process, stopper.current_jobs['crash'])
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # test BACKOFF process: segv (last process of this application)
        process = self._get_test_process('segv')
        self.assertIn(process, stopper.current_jobs['crash'])
        stopper.on_event(process)
        self.assertIn(process, stopper.current_jobs['crash'])
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(0, mocked_init.call_count)
        # with firefox application
        # empty planned_jobs to trigger another behaviour
        stopper.planned_jobs = {}
        # test EXITED / unexpected process: firefox
        process = self._get_test_process('firefox')
        self.assertIn(process, stopper.current_jobs['firefox'])
        stopper.on_event(process)
        self.assertNotIn('firefox', stopper.current_jobs.keys())
        self.assertEqual(0, mocked_process.call_count)
        self.assertEqual(1, mocked_init.call_count)

    def test_store_application_stop_sequence(self):
        """ Test the store_application_stop_sequence method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Stopper
        stopper = Stopper(self.supvisors)
        # create 2 application start_sequences
        application1 = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for process in self.process_list:
            if process.application_name == 'sample_test_1':
                application1.stop_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        application2 = ApplicationStatus('sample_test_2', self.supvisors.logger)
        for process in self.process_list:
            if process.application_name == 'sample_test_2':
                application2.stop_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        # call method ans check result
        stopper.store_application_stop_sequence(application1)
        # check application sequence in stopper planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'], 2: ['sample_test_1:xclock']}}},
            stopper.printable_planned_sequence())
        # call method a second time and check result
        stopper.store_application_stop_sequence(application2)
        # check application sequence in stopper planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'], 2: ['sample_test_1:xclock']},
                'sample_test_2': {0: ['sample_test_2:yeux_00', 'sample_test_2:yeux_01'], 1: ['sample_test_2:sleep']}}},
            stopper.printable_planned_sequence())

    def test_force_process_unknown(self):
        """ Test the force_process_unknown method. """
        from supvisors.commander import Stopper
        # create the instance
        stopper = Stopper(self.supvisors)
        # get patches
        mocked_listener = self.supvisors.listener.force_process_unknown
        mocked_source = self.supvisors.info_source.force_process_unknown
        # test with no info_source KeyError
        stopper.force_process_unknown('proc', 'any reason')
        self.assertEqual(1, mocked_source.call_count)
        self.assertEqual([call('proc', 'any reason')], mocked_source.call_args_list)
        self.assertEqual(0, mocked_listener.call_count)
        mocked_source.reset_mock()
        # test force_process_unknown with info_source KeyError
        mocked_source.side_effect = KeyError
        stopper.force_process_unknown('proc', 'any reason')
        self.assertEqual(1, mocked_source.call_count)
        self.assertEqual([call('proc', 'any reason')], mocked_source.call_args_list)
        self.assertEqual([call('proc')], mocked_listener.call_args_list)

    def test_process_job(self):
        """ Test the process_job method. """
        from supvisors.commander import Stopper
        stopper = Stopper(self.supvisors)
        # get patches
        mocked_pusher = self.supvisors.zmq.pusher.send_stop_process
        # test with stopped process
        process = self._get_test_process('xlogo')
        jobs = []
        stopper.process_job(process, jobs) 
        self.assertListEqual([], jobs)
        self.assertEqual(0, mocked_pusher.call_count)
        # test with running process
        process = self._get_test_process('xfontsel')
        jobs = []
        stopper.process_job(process, jobs)
        self.assertListEqual([process], jobs)
        self.assertEqual([call('10.0.0.1', 'sample_test_1:xfontsel')],
            mocked_pusher.call_args_list)

    def test_stop_process(self):
        """ Test the stop_process method. """
        from supvisors.commander import Stopper
        stopper = Stopper(self.supvisors)
        # get any process
        xlogo_process = self._get_test_process('xlogo')
        # test failure
        with patch.object(stopper, 'process_job') as mocked_jobs:
            start_result = stopper.stop_process(xlogo_process)
            self.assertDictEqual({}, stopper.current_jobs)
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertTrue(start_result)
        # test success
        def success_job(*args, **kwargs):
            args[1].append(args[0])
        with patch.object(stopper, 'process_job', side_effect=success_job) as mocked_jobs:
            start_result = stopper.stop_process(xlogo_process)
            self.assertDictEqual({'sample_test_1': [xlogo_process]}, stopper.current_jobs)
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertFalse(start_result)
            # get any other process
            yeux_process = self._get_test_process('yeux_00')
            # test that success complements current_jobs
            start_result = stopper.stop_process(yeux_process)
            self.assertDictEqual({'sample_test_1': [xlogo_process], 'sample_test_2': [yeux_process]},
                stopper.current_jobs)
            self.assertEqual(2, mocked_jobs.call_count)
            self.assertFalse(start_result)

    def test_stop_application(self):
        """ Test the stop_application method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Stopper
        from supvisors.ttypes import ApplicationStates
        stopper = Stopper(self.supvisors)
        # create application start_sequence
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for process in self.process_list:
            if process.application_name == 'sample_test_1':
                application.stop_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        # patch the starter.process_application_jobs
        def success_job(*args, **kwargs):
            args[1].append(args[0])
        with patch.object(stopper, 'process_job', side_effect=success_job) as mocked_jobs:
            # test start_application on a stopped application
            application._state = ApplicationStates.STOPPED
            test_result = stopper.stop_application(application)
            self.assertTrue(test_result)
            self.assertDictEqual({}, stopper.planned_sequence)
            self.assertDictEqual({}, stopper.planned_jobs)
            self.assertDictEqual({}, stopper.current_jobs)
            self.assertEqual(0, mocked_jobs.call_count)
            # test start_application on a stopped application
            application._state = ApplicationStates.RUNNING
            test_result = stopper.stop_application(application)
            self.assertFalse(test_result)
            # only planned jobs and not current jobs because of process_application_jobs patch
            self.assertDictEqual({}, stopper.planned_sequence)
            self.assertDictEqual({'sample_test_1': {2: ['sample_test_1:xclock']}}, stopper.printable_planned_jobs())
            self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo']}, stopper.printable_current_jobs())
            self.assertEqual(2, mocked_jobs.call_count)

    def test_stop_applications(self):
        """ Test the stop_applications method. """
        from supvisors.application import ApplicationStatus
        from supvisors.commander import Stopper
        from supvisors.ttypes import ApplicationStates
        stopper = Stopper(self.supvisors)
        # create one running application with a start_sequence > 0
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        application._state = ApplicationStates.RUNNING
        application.rules.stop_sequence = 2
        self.supvisors.context.applications['sample_test_1'] = application
        for process in self.process_list:
            if process.application_name == 'sample_test_1':
                application.stop_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        # create one stopped application
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_2'] = application
        # create one running application with a start_sequence == 0
        application = ApplicationStatus('crash', self.supvisors.logger)
        application._state = ApplicationStates.RUNNING
        application.rules.stop_sequence = 0
        self.supvisors.context.applications['crash'] = application
        for process in self.process_list:
            if process.application_name == 'crash':
                application.stop_sequence.setdefault(len(process.namespec()) % 3, []).append(process)
        # call starter start_applications and check that only sample_test_2 is triggered
        with patch.object(stopper, 'process_application_jobs') as mocked_jobs:
            stopper.stop_applications()
            self.assertDictEqual({2: {'sample_test_1':
                    {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'], 2: ['sample_test_1:xclock']}}},
                stopper.printable_planned_sequence())
            self.assertDictEqual({'crash': {0: ['crash:late_segv'], 1: ['crash:segv']}},
                stopper.printable_planned_jobs())
            # current jobs is empty because of process_application_jobs mocking
            self.assertDictEqual({}, stopper.printable_current_jobs())
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertEqual(call('crash'), mocked_jobs.call_args)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
