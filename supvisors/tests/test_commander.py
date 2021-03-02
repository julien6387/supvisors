#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from unittest.mock import call, patch, Mock

from supvisors.tests.base import MockedSupvisors, database_copy, CompatTestCase


class ProcessCommandTest(CompatTestCase):
    """ Test case for the ProcessCommand class of the commander module. """

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.commander import ProcessCommand
        from supvisors.ttypes import StartingStrategies
        process = 'a process'
        # test default strategy
        command = ProcessCommand(process)
        self.assertIs(process, command.process)
        self.assertEqual(None, command.strategy)
        self.assertEqual(0, command.request_time)
        self.assertFalse(command.ignore_wait_exit)
        self.assertEqual('', command.extra_args)
        # test strategy in parameter
        command = ProcessCommand(process, StartingStrategies.MOST_LOADED)
        self.assertIs(process, command.process)
        self.assertEqual(StartingStrategies.MOST_LOADED, command.strategy)
        self.assertEqual(0, command.request_time)
        self.assertFalse(command.ignore_wait_exit)
        self.assertEqual('', command.extra_args)

    def test_str(self):
        """ Test the output string of the ProcessCommand. """
        from supvisors.commander import ProcessCommand
        from supvisors.ttypes import StartingStrategies
        process = Mock(state='RUNNING', last_event_time=1234,
                       **{'namespec.return_value': 'proc_1'})
        command = ProcessCommand(process, StartingStrategies.CONFIG)
        command.request_time = 4321
        command.ignore_wait_exit = True
        command.extra_args = '-s test args'
        self.assertEqual('process=proc_1 state=RUNNING last_event_time=1234 '
                         'strategy=0 request_time=4321 ignore_wait_exit=True '
                         'extra_args="-s test args"', str(command))

    def test_timed_out(self):
        """ Test the timed_out method. """
        from supvisors.commander import ProcessCommand
        command = ProcessCommand(Mock(last_event_time=100))
        command.request_time = 95
        self.assertFalse(command.timed_out(102))
        command.request_time = 101
        self.assertFalse(command.timed_out(108))
        self.assertTrue(command.timed_out(112))
        command.request_time = 99
        self.assertTrue(command.timed_out(111))


class CommanderContextTest(CompatTestCase):

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        self.supvisors = MockedSupvisors()
        # store list for tests
        self.command_list = []
        for info in database_copy():
            command = self._create_process_command(info['group'], info['name'])
            command.process.add_info('10.0.0.1', info)
            self.command_list.append(command)

    def _create_process_command(self, group, name):
        """ Create a ProcessCommand from process info. """
        from supvisors.commander import ProcessCommand
        from supvisors.process import ProcessStatus
        process = ProcessStatus(group, name, self.supvisors)
        return ProcessCommand(process)

    def _get_test_command(self, process_name):
        """ Return the first process corresponding to process_name. """
        return next(command for command in self.command_list
                    if command.process.process_name == process_name)


class CommanderTest(CommanderContextTest):
    """ Test case for the Commander class of the commander module. """

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        CommanderContextTest.setUp(self)
        # create the instance to test
        from supvisors.commander import Commander
        self.commander = Commander(self.supvisors)
        # store lists for tests
        self.command_list_1 = [self._create_process_command('appli_A', 'dummy_A1'),
                               self._create_process_command('appli_A', 'dummy_A2'),
                               self._create_process_command('appli_A', 'dummy_A3')]
        self.command_list_2 = [self._create_process_command('appli_B', 'dummy_B1')]

    def test_creation(self):
        """ Test the values set at construction. """
        self.assertIs(self.supvisors, self.commander.supvisors)
        self.assertIs(self.supvisors.logger, self.commander.logger)
        self.assertDictEqual({}, self.commander.planned_sequence)
        self.assertDictEqual({}, self.commander.planned_jobs)
        self.assertDictEqual({}, self.commander.current_jobs)

    def test_in_progress(self):
        """ Test the in_progress method. """
        self.assertFalse(self.commander.in_progress())
        self.commander.planned_sequence = {0: {'if': {0: self.command_list_1}}}
        self.assertTrue(self.commander.in_progress())
        self.commander.planned_jobs = {'then': {1: self.command_list_2}}
        self.assertTrue(self.commander.in_progress())
        self.commander.current_jobs = {'else': []}
        self.assertTrue(self.commander.in_progress())
        self.commander.planned_sequence = {}
        self.assertTrue(self.commander.in_progress())
        self.commander.planned_jobs = {}
        self.assertTrue(self.commander.in_progress())
        self.commander.current_jobs = {}
        self.assertFalse(self.commander.in_progress())

    def test_has_application(self):
        """ Test the has_application method. """
        self.assertFalse(self.commander.has_application('if'))
        self.assertFalse(self.commander.has_application('then'))
        self.assertFalse(self.commander.has_application('else'))
        self.commander.planned_sequence = {0: {'if': {0: self.command_list_1}}}
        self.assertTrue(self.commander.has_application('if'))
        self.assertFalse(self.commander.has_application('then'))
        self.commander.planned_jobs = {'then': {1: self.command_list_2}}
        self.assertTrue(self.commander.has_application('if'))
        self.assertTrue(self.commander.has_application('then'))
        self.assertFalse(self.commander.has_application('else'))
        self.commander.current_jobs = {'else': []}
        self.assertTrue(self.commander.has_application('if'))
        self.assertTrue(self.commander.has_application('then'))
        self.assertTrue(self.commander.has_application('else'))
        self.commander.planned_sequence = {}
        self.assertFalse(self.commander.has_application('if'))
        self.assertTrue(self.commander.has_application('then'))
        self.assertTrue(self.commander.has_application('else'))
        self.commander.planned_jobs = {}
        self.assertFalse(self.commander.has_application('if'))
        self.assertFalse(self.commander.has_application('then'))
        self.assertTrue(self.commander.has_application('else'))
        self.commander.current_jobs = {}
        self.assertFalse(self.commander.has_application('if'))
        self.assertFalse(self.commander.has_application('then'))
        self.assertFalse(self.commander.has_application('else'))

    def test_printable_command_list(self):
        """ Test the printable_process_list method. """
        from supvisors.commander import Commander
        # test with empty list
        printable = Commander.printable_command_list([])
        self.assertListEqual([], printable)
        # test with list having a single element
        printable = Commander.printable_command_list(self.command_list_2)
        self.assertListEqual(['appli_B:dummy_B1'], printable)
        # test with list having multiple elements
        printable = Commander.printable_command_list(self.command_list_1)
        self.assertListEqual(['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'], printable)

    def test_printable_current_jobs(self):
        """ Test the printable_current_jobs method. """
        # test with empty structure
        self.commander.current_jobs = {}
        printable = self.commander.printable_current_jobs()
        self.assertDictEqual({}, printable)
        # test with complex structure
        self.commander.current_jobs = {'if': [],
                                       'then': self.command_list_1,
                                       'else': self.command_list_2}
        printable = self.commander.printable_current_jobs()
        self.assertDictEqual({'if': [],
                              'then': ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3'],
                              'else': ['appli_B:dummy_B1']}, printable)

    def test_printable_planned_jobs(self):
        """ Test the printable_planned_jobs method. """
        # test with empty structure
        self.commander.planned_jobs = {}
        printable = self.commander.printable_planned_jobs()
        self.assertDictEqual({}, printable)
        # test with complex structure
        self.commander.planned_jobs = {'if': {0: self.command_list_1, 1: []},
                                       'then': {2: self.command_list_2},
                                       'else': {}}
        printable = self.commander.printable_planned_jobs()
        self.assertDictEqual({'if': {0: ['appli_A:dummy_A1',
                                         'appli_A:dummy_A2',
                                         'appli_A:dummy_A3'], 1: []},
                              'then': {2: ['appli_B:dummy_B1']}, 'else': {}}, printable)

    def test_printable_planned_sequence(self):
        """ Test the printable_planned_sequence method. """
        # test with empty structure
        self.commander.planned_sequence = {}
        printable = self.commander.printable_planned_sequence()
        self.assertDictEqual({}, printable)
        # test with complex structure
        self.commander.planned_sequence = {0: {'if': {-1: [], 0: self.command_list_1},
                                               'then': {2: self.command_list_2}},
                                           3: {'else': {}}}
        printable = self.commander.printable_planned_sequence()
        self.assertDictEqual({0: {'if': {-1: [], 0: ['appli_A:dummy_A1', 'appli_A:dummy_A2', 'appli_A:dummy_A3']},
                                  'then': {2: ['appli_B:dummy_B1']}},
                              3: {'else': {}}}, printable)

    def test_process_application_jobs(self):
        """ Test the process_application_jobs method. """
        # fill planned_jobs
        self.commander.planned_jobs = {'if': {0: self.command_list_1, 1: []},
                                       'then': {2: self.command_list_2},
                                       'else': {}}

        # define patch function
        def fill_jobs(*args, **kwargs):
            args[1].append(args[0])

        with patch.object(self.commander, 'process_job', side_effect=fill_jobs) as mocked_job:
            # test with unknown application
            self.commander.process_application_jobs('while')
            self.assertDictEqual({}, self.commander.current_jobs)
            self.assertDictEqual({'if': {0: self.command_list_1, 1: []},
                                  'then': {2: self.command_list_2},
                                  'else': {}},
                                 self.commander.planned_jobs)
            self.assertEqual(0, mocked_job.call_count)
            # test with known application: sequence 0 of 'if' application is popped
            self.commander.process_application_jobs('if')
            self.assertDictEqual({'if': {1: []},
                                  'then': {2: self.command_list_2},
                                  'else': {}}, self.commander.planned_jobs)
            self.assertDictEqual({'if': self.command_list_1}, self.commander.current_jobs)
            self.assertEqual(3, mocked_job.call_count)
            # test with known application: sequence 1 of 'if' application is popped
            mocked_job.reset_mock()
            self.commander.process_application_jobs('if')
            self.assertDictEqual({'then': {2: self.command_list_2}, 'else': {}},
                                 self.commander.planned_jobs)
            self.assertDictEqual({}, self.commander.current_jobs)
            self.assertEqual(0, mocked_job.call_count)
        # test that process_job method must be implemented
        with self.assertRaises(NotImplementedError):
            self.commander.process_application_jobs('then')
        self.assertDictEqual({'then': {}, 'else': {}}, self.commander.planned_jobs)
        self.assertDictEqual({'then': []}, self.commander.current_jobs)

    def test_trigger_jobs(self):
        """ Test the trigger_jobs method. """
        # test with empty structure
        self.commander.planned_sequence = {}
        self.commander.trigger_jobs()
        self.assertDictEqual({}, self.commander.planned_jobs)
        # test with complex structure
        self.commander.planned_sequence = {0: {'if': {2: [], 0: self.command_list_1},
                                               'then': {2: self.command_list_2}},
                                           3: {'else': {}}}

        # define patch function
        def fill_jobs(*args, **kwargs):
            args[1].append(args[0])

        with patch.object(self.commander, 'process_job', side_effect=fill_jobs) as mocked_job:
            self.commander.trigger_jobs()
            # test impact on internal attributes
            self.assertDictEqual({3: {'else': {}}}, self.commander.planned_sequence)
            self.assertDictEqual({'if': {2: []}}, self.commander.planned_jobs)
            self.assertDictEqual({'if': self.command_list_1, 'then': self.command_list_2},
                                 self.commander.current_jobs)
            self.assertEqual(4, mocked_job.call_count)

    @patch('supvisors.commander.Commander.trigger_jobs')
    @patch('supvisors.commander.Commander.force_process_state')
    @patch('supvisors.commander.Commander.after_event')
    def test_check_progress(self, mocked_after: Mock, mocked_force: Mock, mocked_trigger: Mock):
        """ Test the check_progress method. """
        from supvisors.ttypes import ProcessStates
        # test with no sequence in progress
        self.assertTrue(self.commander.check_progress('stopped', ProcessStates.FATAL))
        # test with no current jobs but planned sequence and no planned jobs
        self.commander.planned_sequence = {3: {'else': {}}}
        self.assertFalse(self.commander.check_progress('stopped', ProcessStates.FATAL))
        self.assertEqual([call()], mocked_trigger.call_args_list)
        mocked_trigger.reset_mock()
        # test with no current jobs but planned sequence and planned jobs (unexpected case)
        self.commander.planned_jobs = {'if': {2: []}}
        self.assertFalse(self.commander.check_progress('stopped', ProcessStates.FATAL))
        self.assertFalse(mocked_trigger.called)
        # set test current_jobs
        # xfontsel is RUNNING, xlogo is STOPPED, yeux_00 is EXITED, yeux_01 is RUNNING
        self.commander.current_jobs = {'sample_test_1': [self._get_test_command('xfontsel'),
                                                         self._get_test_command('xlogo')],
                                       'sample_test_2': [self._get_test_command('yeux_00'),
                                                         self._get_test_command('yeux_01')]}
        # assign request_time to processes in current_jobs
        for command_list in self.commander.current_jobs.values():
            for command in command_list:
                command.request_time = time.time()
        # stopped processes have a recent request time: nothing done
        completed = self.commander.check_progress('stopped', ProcessStates.FATAL)
        self.assertFalse(completed)
        self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                              'sample_test_2': ['sample_test_2:yeux_00', 'sample_test_2:yeux_01']},
                             self.commander.printable_current_jobs())
        self.assertFalse(mocked_force.called)
        self.assertFalse(mocked_after.called)
        self.assertFalse(mocked_trigger.called)
        # re-assign last_event_time and request_time to processes in current_jobs
        for command_list in self.commander.current_jobs.values():
            for command in command_list:
                command.process.last_event_time = 0
                command.request_time = 0
        # stopped processes have an old request time: actions taken on state and sequence
        completed = self.commander.check_progress('stopped', ProcessStates.FATAL)
        self.assertFalse(completed)
        self.assertEqual({'sample_test_1': ['sample_test_1:xfontsel'], 'sample_test_2': ['sample_test_2:yeux_01']},
                         self.commander.printable_current_jobs())
        reason = 'Still stopped 10 seconds after request'
        self.assertEqual([call('sample_test_1:xlogo', ProcessStates.FATAL, reason),
                          call('sample_test_2:yeux_00', ProcessStates.FATAL, reason)],
                         mocked_force.call_args_list)
        self.assertFalse(mocked_after.called)
        self.assertFalse(mocked_trigger.called)
        # reset mocks
        mocked_force.reset_mock()
        # re-assign request_time to processes in remaining current_jobs
        for command_list in self.commander.current_jobs.values():
            for command in command_list:
                command.request_time = time.time()
        # stopped processes have a recent request time: nothing done
        completed = self.commander.check_progress('running', ProcessStates.UNKNOWN)
        self.assertFalse(completed)
        self.assertEqual({'sample_test_1': ['sample_test_1:xfontsel'], 'sample_test_2': ['sample_test_2:yeux_01']},
                         self.commander.printable_current_jobs())
        self.assertFalse(mocked_force.called)
        self.assertFalse(mocked_after.called)
        self.assertFalse(mocked_trigger.called)
        # re-assign last_event_time and request_time to processes in current_jobs
        for command_list in self.commander.current_jobs.values():
            for command in command_list:
                command.process.last_event_time = 0
                command.request_time = 0
        # stopped processes have an old request time: actions taken on state and sequence
        completed = self.commander.check_progress('running', ProcessStates.UNKNOWN)
        self.assertFalse(completed)
        self.assertEqual({'sample_test_1': [], 'sample_test_2': []},
                         self.commander.printable_current_jobs())
        reason = 'Still running 10 seconds after request'
        self.assertEqual([call('sample_test_1:xfontsel', ProcessStates.UNKNOWN, reason),
                          call('sample_test_2:yeux_01', ProcessStates.UNKNOWN, reason)],
                         mocked_force.call_args_list)
        self.assertEqual([call('sample_test_1'), call('sample_test_2')], mocked_after.call_args_list)
        self.assertFalse(mocked_trigger.called)

    @patch('supvisors.infosource.SupervisordSource.force_process_fatal')
    @patch('supvisors.listener.SupervisorListener.force_process_fatal')
    def test_force_process_fatal(self, mocked_listener, mocked_source):
        """ Test the force_process_state method with a FATAL parameter. """
        from supvisors.ttypes import ProcessStates
        # test with FATAL and no info_source KeyError
        self.commander.force_process_state('proc', ProcessStates.FATAL, 'any reason')
        self.assertEqual([call(self.supvisors.info_source, 'proc', 'any reason')], mocked_source.call_args_list)
        self.assertFalse(mocked_listener.called)
        mocked_source.reset_mock()
        # test with FATAL and info_source KeyError
        mocked_source.side_effect = KeyError
        self.commander.force_process_state('proc', ProcessStates.FATAL, 'any reason')
        self.assertEqual([call(self.supvisors.info_source, 'proc', 'any reason')], mocked_source.call_args_list)
        self.assertEqual([call(self.supvisors.listener, 'proc')], mocked_listener.call_args_list)

    @patch('supvisors.infosource.SupervisordSource.force_process_unknown')
    @patch('supvisors.listener.SupervisorListener.force_process_unknown')
    def test_force_process_unknown(self, mocked_listener, mocked_source):
        """ Test the force_process_state method with an UNKNOWN parameter. """
        from supvisors.ttypes import ProcessStates
        # test with UNKNOWN and no info_source KeyError
        self.commander.force_process_state('proc', ProcessStates.UNKNOWN, 'any reason')
        self.assertEqual([call(self.supvisors.info_source, 'proc', 'any reason')], mocked_source.call_args_list)
        self.assertFalse(mocked_listener.called)
        mocked_source.reset_mock()
        # test with UNKNOWN and info_source KeyError
        mocked_source.side_effect = KeyError
        self.commander.force_process_state('proc', ProcessStates.UNKNOWN, 'any reason')
        self.assertEqual([call(self.supvisors.info_source, 'proc', 'any reason')], mocked_source.call_args_list)
        self.assertEqual([call(self.supvisors.listener, 'proc')], mocked_listener.call_args_list)

    @patch('supvisors.commander.Commander.process_application_jobs')
    @patch('supvisors.commander.Commander.trigger_jobs')
    def test_after_event(self, mocked_trigger: Mock, mocked_process: Mock):
        """ Test the after_event method. """
        # prepare some context
        self.commander.planned_jobs = {'if': {2: []}}
        self.commander.current_jobs = {'if': [], 'then': [], 'else': []}
        # test after_event when there are still planned jobs for application
        self.commander.after_event('if')
        self.assertNotIn('if', self.commander.current_jobs)
        self.assertEqual([call('if')], mocked_process.call_args_list)
        self.assertFalse(mocked_trigger.called)
        # reset mocks
        mocked_process.reset_mock()
        # test after_event when there's no more planned jobs for this application
        self.commander.after_event('then')
        self.assertNotIn('then', self.commander.current_jobs)
        self.assertFalse(mocked_process.called)
        self.assertFalse(mocked_trigger.called)
        # test after_event when there's no more planned jobs at all
        self.commander.planned_jobs = {}
        self.commander.after_event('else')
        self.assertNotIn('else', self.commander.current_jobs)
        self.assertFalse(mocked_process.called)
        self.assertFalse(mocked_process.called)
        self.assertEqual([call()], mocked_trigger.call_args_list)


class StarterTest(CommanderContextTest):
    """ Test case for the Starter class of the commander module. """

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        CommanderContextTest.setUp(self)
        from supvisors.commander import Starter
        self.starter = Starter(self.supvisors)

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.commander import Commander
        self.assertIsInstance(self.starter, Commander)

    def test_abort(self):
        """ Test the abort method. """
        # prepare some context
        self.starter.planned_sequence = {3: {'else': {}}}
        self.starter.planned_jobs = {'if': {2: []}}
        self.starter.current_jobs = {'if': ['dummy_1', 'dummy_2'], 'then': ['dummy_3']}
        # call abort and check attributes
        self.starter.abort()
        self.assertDictEqual({}, self.starter.planned_sequence)
        self.assertDictEqual({}, self.starter.planned_jobs)
        self.assertDictEqual({}, self.starter.current_jobs)

    def test_store_application_start_sequence(self):
        """ Test the store_application_start_sequence method. """
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import StartingStrategies
        # create 2 application start_sequences
        appli1 = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for command in self.command_list:
            if command.process.application_name == 'sample_test_1':
                appli1.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        appli2 = ApplicationStatus('sample_test_2', self.supvisors.logger)
        for command in self.command_list:
            if command.process.application_name == 'sample_test_2':
                appli2.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        # call method and check result
        self.starter.store_application_start_sequence(appli1, StartingStrategies.LESS_LOADED)
        # check that application sequence 0 is not in starter planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                    2: ['sample_test_1:xclock']}}},
                             self.starter.printable_planned_sequence())
        # check strategy applied
        for proc_list in self.starter.planned_sequence[0]['sample_test_1'].values():
            for proc in proc_list:
                self.assertEqual(StartingStrategies.LESS_LOADED, proc.strategy)
        # call method a second time and check result
        self.starter.store_application_start_sequence(appli2, StartingStrategies.LOCAL)
        # check that application sequence 0 is not in starter planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                    2: ['sample_test_1:xclock']},
                                  'sample_test_2': {1: ['sample_test_2:sleep']}}},
                             self.starter.printable_planned_sequence())
        # check strategy applied
        for proc_list in self.starter.planned_sequence[0]['sample_test_1'].values():
            for proc in proc_list:
                self.assertEqual(StartingStrategies.LESS_LOADED, proc.strategy)
        for proc_list in self.starter.planned_sequence[0]['sample_test_2'].values():
            for proc in proc_list:
                self.assertEqual(StartingStrategies.LOCAL, proc.strategy)

    def test_process_failure_optional(self):
        """ Test the process_failure method with an optional process. """
        # prepare context
        process = Mock()
        process.rules = Mock(required=False)
        test_planned_jobs = {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
        # get the patch for stopper / stop_application
        mocked_stopper = self.supvisors.stopper.stop_application
        # test with a process not required
        self.starter.planned_jobs = test_planned_jobs.copy()
        self.starter.process_failure(process)
        # test planned_jobs is unchanged
        self.assertDictEqual(test_planned_jobs, self.starter.planned_jobs)
        # test stop_application is not called
        self.assertEqual(0, mocked_stopper.call_count)

    def test_process_failure_required(self):
        """ Test the process_failure method with a required process. """
        from supvisors.ttypes import StartingFailureStrategies
        # prepare context
        process = Mock(application_name='appli_1')
        process.rules = Mock(required=True)
        application = Mock()
        self.supvisors.context.applications = {'appli_1': application, 'proc_2': None}
        test_planned_jobs = {'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}}
        # get the patch for stopper / stop_application
        mocked_stopper = self.supvisors.stopper.stop_application
        # test ABORT starting strategy
        self.starter.planned_jobs = test_planned_jobs.copy()
        application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.ABORT)
        self.starter.process_failure(process)
        # check that application has been removed from planned jobs and stopper wasn't called
        self.assertDictEqual({'appli_2': {1: ['proc_2']}}, self.starter.planned_jobs)
        self.assertEqual(0, mocked_stopper.call_count)
        # test CONTINUE starting strategy
        self.starter.planned_jobs = test_planned_jobs.copy()
        application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.CONTINUE)
        self.starter.process_failure(process)
        # check that application has NOT been removed from planned jobs and stopper wasn't called
        self.assertDictEqual({'appli_1': {0: ['proc_1']}, 'appli_2': {1: ['proc_2']}},
                             self.starter.planned_jobs)
        self.assertEqual(0, mocked_stopper.call_count)
        # test STOP starting strategy
        self.starter.planned_jobs = test_planned_jobs.copy()
        application.rules = Mock(starting_failure_strategy=StartingFailureStrategies.STOP)
        self.starter.process_failure(process)
        # check that application has been removed from planned jobs and stopper has been called
        self.assertDictEqual({'appli_2': {1: ['proc_2']}}, self.starter.planned_jobs)
        self.assertEqual([call(application)], mocked_stopper.call_args_list)

    @patch('supvisors.commander.Commander.check_progress', return_value=True)
    def test_check_starting(self, mocked_check: Mock):
        """ Test the check_starting method. """
        from supvisors.ttypes import ProcessStates
        self.assertTrue(self.starter.check_starting())
        self.assertEqual([call('stopped', ProcessStates.FATAL)], mocked_check.call_args_list)

    def test_on_event(self):
        """ Test the on_event method. """
        # apply patches
        with patch.object(self.starter, 'on_event_in_sequence') as mocked_in:
            with patch.object(self.starter, 'on_event_out_of_sequence') as mocked_out:
                # set test current_jobs
                for command in self.command_list:
                    self.starter.current_jobs.setdefault(command.process.application_name, []).append(command)
                self.assertIn('sample_test_1', self.starter.current_jobs)
                # test that on_event_out_of_sequence is called when process
                # is not in current jobs due to unknown application
                process = Mock(application_name='unknown_application')
                self.starter.on_event(process)
                self.assertEqual(0, mocked_in.call_count)
                self.assertEqual([(call(process))], mocked_out.call_args_list)
                mocked_out.reset_mock()
                # test that on_event_out_of_sequence is called when process
                # is not in current jobs due to unknown process
                process = Mock(application_name='sample_test_1')
                self.starter.on_event(process)
                self.assertEqual(0, mocked_in.call_count)
                self.assertEqual([(call(process))], mocked_out.call_args_list)
                mocked_out.reset_mock()
                # test that on_event_in_sequence is called when process is in list
                jobs = self.starter.current_jobs['sample_test_1']
                command = next(iter(jobs))
                self.starter.on_event(command.process)
                self.assertEqual(0, mocked_out.call_count)
                self.assertEqual([(call(command, jobs))], mocked_in.call_args_list)

    @patch('supvisors.commander.Starter.process_failure')
    @patch('supvisors.commander.Commander.after_event')
    def test_on_event_in_sequence(self, mocked_after: Mock, mocked_failure: Mock):
        """ Test the on_event_in_sequence method. """
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import StartingFailureStrategies
        # set context for current_jobs
        for command in self.command_list:
            self.starter.current_jobs.setdefault(command.process.application_name, []).append(command)
        # add application context
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        application.rules.starting_failure_strategy = StartingFailureStrategies.CONTINUE
        self.supvisors.context.applications['sample_test_1'] = application
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        application.rules.starting_failure_strategy = StartingFailureStrategies.ABORT
        self.supvisors.context.applications['sample_test_2'] = application
        # with sample_test_1 application
        # test STOPPED process
        command = self._get_test_command('xlogo')
        jobs = self.starter.current_jobs['sample_test_1']
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertFalse(command.ignore_wait_exit)
        self.assertNotIn(command, jobs)
        self.assertEqual([call(command.process)], mocked_failure.call_args_list)
        self.assertFalse(mocked_after.called)
        # reset mocks
        mocked_failure.reset_mock()
        # test STOPPING process: xclock
        command = self._get_test_command('xclock')
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertFalse(command.ignore_wait_exit)
        self.assertNotIn(command, jobs)
        self.assertEqual([call(command.process)], mocked_failure.call_args_list)
        self.assertFalse(mocked_after.called)
        # reset mocks
        mocked_failure.reset_mock()
        # test RUNNING process: xfontsel (last process of this application)
        command = self._get_test_command('xfontsel')
        self.assertIn(command, jobs)
        self.assertFalse(command.process.rules.wait_exit)
        self.assertFalse(command.ignore_wait_exit)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertNotIn(command, jobs)
        self.assertFalse(mocked_failure.called)
        self.assertEqual([call('sample_test_1')], mocked_after.call_args_list)
        # reset mocks
        mocked_after.reset_mock()
        # with sample_test_2 application
        # test RUNNING process: yeux_01
        command = self._get_test_command('yeux_01')
        jobs = self.starter.current_jobs['sample_test_2']
        command.process.rules.wait_exit = True
        command.ignore_wait_exit = True
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertNotIn(command, jobs)
        self.assertFalse(mocked_failure.called)
        self.assertFalse(mocked_after.called)
        # test EXITED / expected process: yeux_00
        command = self._get_test_command('yeux_00')
        command.process.rules.wait_exit = True
        command.process.expected_exit = True
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertNotIn(command, jobs)
        self.assertFalse(mocked_failure.called)
        self.assertFalse(mocked_after.called)
        # test FATAL process: sleep (last process of this application)
        command = self._get_test_command('sleep')
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertFalse(command.ignore_wait_exit)
        self.assertNotIn(command, jobs)
        self.assertEqual([call(command.process)], mocked_failure.call_args_list)
        self.assertEqual([call('sample_test_2')], mocked_after.call_args_list)
        # reset mocks
        mocked_failure.reset_mock()
        mocked_after.reset_mock()
        # with crash application
        # test STARTING process: late_segv
        command = self._get_test_command('late_segv')
        jobs = self.starter.current_jobs['crash']
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertIn(command, jobs)
        self.assertFalse(mocked_failure.called)
        self.assertFalse(mocked_after.called)
        # test BACKOFF process: segv (last process of this application)
        command = self._get_test_command('segv')
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertIn(command, jobs)
        self.assertFalse(mocked_failure.called)
        self.assertFalse(mocked_after.called)
        # with firefox application
        # test EXITED / unexpected process: firefox
        command = self._get_test_command('firefox')
        jobs = self.starter.current_jobs['firefox']
        command.process.rules.wait_exit = True
        command.process.expected_exit = False
        self.assertIn(command, jobs)
        self.starter.on_event_in_sequence(command, jobs)
        self.assertIn('firefox', self.starter.current_jobs)
        self.assertEqual([call(command.process)], mocked_failure.call_args_list)
        self.assertEqual([call('firefox')], mocked_after.call_args_list)

    def test_on_event_out_of_sequence(self):
        """ Test how failure are raised in on_event_out_of_sequence method. """
        # set test planned_jobs and current_jobs
        self.starter.planned_jobs = {'sample_test_2': {1: []}}
        for command in self.command_list:
            self.starter.current_jobs.setdefault(command.process.application_name, []).append(command)
        # apply patch
        with patch.object(self.starter, 'process_failure') as mocked_failure:
            # test that process_failure is not called if process is not crashed
            process = next(command.process
                           for command in self.command_list
                           if not command.process.crashed())
            self.starter.on_event_out_of_sequence(process)
            self.assertEqual(0, mocked_failure.call_count)
            # test that process_failure is not called if process is not in planned jobs
            process = next(command.process
                           for command in self.command_list
                           if command.process.application_name == 'sample_test_1')
            self.starter.on_event_out_of_sequence(process)
            self.assertEqual(0, mocked_failure.call_count)
            # get a command related to a process crashed and in planned jobs
            command = next(command
                           for command in self.command_list
                           if command.process.crashed() and command.process.application_name == 'sample_test_2')
            # test that process_failure is called if process' starting is not planned
            self.starter.on_event_out_of_sequence(command.process)
            self.assertEqual([(call(command.process))], mocked_failure.call_args_list)
            mocked_failure.reset_mock()
            # test that process_failure is not called if process' starting is still planned
            self.starter.planned_jobs = {'sample_test_2': {1: [command]}}
            self.starter.on_event_out_of_sequence(command.process)
            self.assertEqual(0, mocked_failure.call_count)

    @patch('supvisors.commander.Commander.force_process_state')
    @patch('supvisors.commander.get_address')
    def test_process_job(self, mocked_address: Mock, mocked_force: Mock):
        """ Test the process_job method. """
        from supvisors.ttypes import ProcessStates
        # get patches
        mocked_pusher = self.supvisors.zmq.pusher.send_start_process
        # test with a possible starting address
        mocked_address.return_value = '10.0.0.1'
        # 1. test with running process
        command = self._get_test_command('xfontsel')
        command.ignore_wait_exit = True
        jobs = []
        # call the process_jobs
        self.starter.process_job(command, jobs)
        # starting methods are not called
        self.assertListEqual([], jobs)
        self.assertEqual(0, mocked_address.call_count)
        self.assertEqual(0, mocked_pusher.call_count)
        # failure method is not called
        self.assertEqual(0, mocked_force.call_count)
        # 2. test with stopped process
        command = self._get_test_command('xlogo')
        command.ignore_wait_exit = True
        jobs = []
        # call the process_jobs
        self.starter.process_job(command, jobs)
        # starting methods are called
        self.assertListEqual([command], jobs)
        self.assertEqual([call(self.supvisors, None, ['*'], 1)], mocked_address.call_args_list)
        self.assertEqual(1, mocked_pusher.call_count)
        self.assertEqual(call('10.0.0.1', 'sample_test_1:xlogo', ''), mocked_pusher.call_args)
        mocked_pusher.reset_mock()
        # failure method is not called
        self.assertEqual(0, mocked_force.call_count)
        # test with no starting address
        mocked_address.return_value = None
        # test with stopped process
        command = self._get_test_command('xlogo')
        command.ignore_wait_exit = True
        jobs = []
        # call the process_jobs
        self.starter.process_job(command, jobs)
        # starting methods are not called but job is in list though
        self.assertListEqual([command], jobs)
        self.assertEqual(0, mocked_pusher.call_count)
        # failure method is called
        self.assertEqual([call('sample_test_1:xlogo', ProcessStates.FATAL, 'no resource available')],
                         mocked_force.call_args_list)

    def test_start_process(self):
        """ Test the start_process method. """
        from supvisors.ttypes import StartingStrategies
        # get any process
        xlogo_command = self._get_test_command('xlogo')
        # test failure
        with patch.object(self.starter, 'process_job', return_value=False) as mocked_jobs:
            start_result = self.starter.start_process(StartingStrategies.CONFIG,
                                                      xlogo_command.process,
                                                      'extra_args')
            self.assertDictEqual({}, self.starter.current_jobs)
            self.assertEqual(1, mocked_jobs.call_count)
            args, kwargs = mocked_jobs.call_args
            self.assertEqual(StartingStrategies.CONFIG, args[0].strategy)
            self.assertEqual('extra_args', args[0].extra_args)
            self.assertTrue(args[0].ignore_wait_exit)
            self.assertTrue(start_result)

        # test success
        def success_job(*args, **kwargs):
            args[1].append(args[0])
            return True

        with patch.object(self.starter, 'process_job', side_effect=success_job) as mocked_jobs:
            start_result = self.starter.start_process(StartingStrategies.CONFIG,
                                                      xlogo_command.process,
                                                      'extra_args')
            self.assertEqual(1, mocked_jobs.call_count)
            args1, _ = mocked_jobs.call_args
            self.assertEqual(StartingStrategies.CONFIG, args1[0].strategy)
            self.assertEqual('extra_args', args1[0].extra_args)
            self.assertTrue(args1[0].ignore_wait_exit)
            self.assertDictEqual({'sample_test_1': [args1[0]]}, self.starter.current_jobs)
            self.assertFalse(start_result)
            mocked_jobs.reset_mock()
            # get any other process
            yeux_command = self._get_test_command('yeux_00')
            # test that success complements current_jobs
            start_result = self.starter.start_process(2, yeux_command.process, '')
            self.assertEqual(1, mocked_jobs.call_count)
            args2, _ = mocked_jobs.call_args
            self.assertEqual(2, args2[0].strategy)
            self.assertEqual('', args2[0].extra_args)
            self.assertTrue(args2[0].ignore_wait_exit)
            self.assertDictEqual({'sample_test_1': [args1[0]], 'sample_test_2': [args2[0]]},
                                 self.starter.current_jobs)
            self.assertFalse(start_result)

    def test_default_start_process(self):
        """ Test the default_start_process method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        with patch.object(starter, 'start_process', return_value=True) as mocked_start:
            # test that default_start_process just calls start_process with the default strategy
            process = Mock()
            result = starter.default_start_process(process)
            self.assertTrue(result)
            self.assertEqual([call(self.supvisors.options.starting_strategy, process)],
                             mocked_start.call_args_list)

    def test_start_application(self):
        """ Test the start_application method. """
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import ApplicationStates, StartingStrategies
        # create application start_sequence
        appli = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for command in self.command_list:
            if command.process.application_name == 'sample_test_1':
                appli.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        # patch the starter.process_application_jobs
        with patch.object(self.starter, 'process_application_jobs') as mocked_jobs:
            # test start_application on a running application
            appli._state = ApplicationStates.RUNNING
            test_result = self.starter.start_application(1, appli)
            self.assertTrue(test_result)
            self.assertDictEqual({}, self.starter.planned_sequence)
            self.assertDictEqual({}, self.starter.planned_jobs)
            self.assertEqual(0, mocked_jobs.call_count)
            # test start_application on a stopped application
            appli._state = ApplicationStates.STOPPED
            test_result = self.starter.start_application(1, appli)
            self.assertFalse(test_result)
            # only planned jobs and not current jobs because of process_application_jobs patch
            self.assertDictEqual({}, self.starter.planned_sequence)
            self.assertDictEqual({'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                    2: ['sample_test_1:xclock']}},
                                 self.starter.printable_planned_jobs())
            self.assertEqual([call('sample_test_1')], mocked_jobs.call_args_list)
            # check strategy applied
            for proc_list in self.starter.planned_jobs['sample_test_1'].values():
                for proc in proc_list:
                    self.assertEqual(StartingStrategies.LESS_LOADED, proc.strategy)

    def test_default_start_application(self):
        """ Test the default_start_application method. """
        from supvisors.commander import Starter
        starter = Starter(self.supvisors)
        with patch.object(starter, 'start_application',
                          return_value=True) as mocked_start:
            # test that default_start_application just calls start_application with the default strategy
            application = Mock()
            result = starter.default_start_application(application)
            self.assertTrue(result)
            self.assertEqual([call(self.supvisors.options.starting_strategy, application)],
                             mocked_start.call_args_list)

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
        for command in self.command_list:
            if command.process.application_name == 'sample_test_2':
                application.start_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        self.supvisors.context.applications['sample_test_2'] = application
        # create one stopped application with a start_sequence == 0
        application = ApplicationStatus('crash', self.supvisors.logger)
        application.rules.start_sequence = 0
        self.supvisors.context.applications['crash'] = application
        # call starter start_applications and check that only sample_test_2 is triggered
        with patch.object(starter, 'process_application_jobs') as mocked_jobs:
            starter.start_applications()
            self.assertDictEqual({}, starter.planned_sequence)
            self.assertDictEqual({'sample_test_2': {1: ['sample_test_2:sleep']}},
                                 starter.printable_planned_jobs())
            # current jobs is empty because of process_application_jobs mocking
            self.assertDictEqual({}, starter.printable_current_jobs())
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertEqual(call('sample_test_2'), mocked_jobs.call_args)


class StopperTest(CommanderContextTest):
    """ Test case for the Stopper class of the commander module. """

    def setUp(self):
        """ Create a Supvisors-like structure and test processes. """
        CommanderContextTest.setUp(self)
        from supvisors.commander import Stopper
        self.stopper = Stopper(self.supvisors)

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.commander import Commander
        self.assertIsInstance(self.stopper, Commander)

    @patch('supvisors.commander.Commander.check_progress', return_value=True)
    def test_check_stopping(self, mocked_check: Mock):
        """ Test the check_stopping method. """
        from supvisors.ttypes import ProcessStates
        self.assertTrue(self.stopper.check_stopping())
        self.assertEqual([call('running', ProcessStates.UNKNOWN)], mocked_check.call_args_list)

    @patch('supvisors.commander.Stopper.after_event')
    def test_on_event(self, mocked_after: Mock):
        """ Test the on_event method. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        from supvisors.ttypes import ProcessStates
        # set context in current_jobs
        for command in self.command_list:
            self.stopper.current_jobs.setdefault(command.process.application_name, []).append(command)
        # add application context
        application = ApplicationStatus('sample_test_1', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_1'] = application
        application = ApplicationStatus('sample_test_2', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_2'] = application
        # try with unknown application
        process = ProcessStatus('dummy_application', 'dummy_process', self.supvisors)
        self.stopper.on_event(process)
        self.assertFalse(mocked_after.called)
        # with sample_test_1 application
        # test STOPPED process
        command = self._get_test_command('xlogo')
        self.assertIn(command, self.stopper.current_jobs['sample_test_1'])
        self.stopper.on_event(command.process)
        self.assertNotIn(command.process, self.stopper.current_jobs['sample_test_1'])
        self.assertFalse(mocked_after.called)
        # test STOPPING process: xclock
        command = self._get_test_command('xclock')
        self.assertIn(command, self.stopper.current_jobs['sample_test_1'])
        self.stopper.on_event(command.process)
        self.assertIn(command, self.stopper.current_jobs['sample_test_1'])
        self.assertFalse(mocked_after.called)
        # test RUNNING process: xfontsel
        command = self._get_test_command('xfontsel')
        self.assertIn(command, self.stopper.current_jobs['sample_test_1'])
        self.stopper.on_event(command.process)
        self.assertIn('sample_test_1', self.stopper.current_jobs.keys())
        self.assertFalse(mocked_after.called)
        # with sample_test_2 application
        # test EXITED / expected process: yeux_00
        command = self._get_test_command('yeux_00')
        self.assertIn(command, self.stopper.current_jobs['sample_test_2'])
        self.stopper.on_event(command.process)
        self.assertNotIn(command, self.stopper.current_jobs['sample_test_2'])
        self.assertFalse(mocked_after.called)
        # test FATAL process: sleep
        command = self._get_test_command('sleep')
        self.assertIn(command, self.stopper.current_jobs['sample_test_2'])
        self.stopper.on_event(command.process)
        self.assertIn('sample_test_2', self.stopper.current_jobs.keys())
        self.assertFalse(mocked_after.called)
        # test RUNNING process: yeux_01
        command = self._get_test_command('yeux_01')
        self.assertIn(command, self.stopper.current_jobs['sample_test_2'])
        self.stopper.on_event(command.process)
        self.assertIn(command, self.stopper.current_jobs['sample_test_2'])
        self.assertFalse(mocked_after.called)
        # force yeux_01 state and re-test
        command.process._state = ProcessStates.STOPPED
        self.assertIn(command, self.stopper.current_jobs['sample_test_2'])
        self.stopper.on_event(command.process)
        self.assertNotIn(command, self.stopper.current_jobs['sample_test_2'])
        self.assertEqual([call('sample_test_2')], mocked_after.call_args_list)
        # reset resources
        mocked_after.reset_mock()
        # with crash application
        # test STARTING process: late_segv
        command = self._get_test_command('late_segv')
        self.assertIn(command, self.stopper.current_jobs['crash'])
        self.stopper.on_event(command.process)
        self.assertIn(command, self.stopper.current_jobs['crash'])
        self.assertFalse(mocked_after.called)
        # test BACKOFF process: segv (last process of this application)
        command = self._get_test_command('segv')
        self.assertIn(command, self.stopper.current_jobs['crash'])
        self.stopper.on_event(command.process)
        self.assertIn(command, self.stopper.current_jobs['crash'])
        self.assertFalse(mocked_after.called)

    def test_store_application_stop_sequence(self):
        """ Test the store_application_stop_sequence method. """
        from supvisors.application import ApplicationStatus
        # create 2 application start_sequences
        appli1 = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for command in self.command_list:
            if command.process.application_name == 'sample_test_1':
                appli1.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        appli2 = ApplicationStatus('sample_test_2', self.supvisors.logger)
        for command in self.command_list:
            if command.process.application_name == 'sample_test_2':
                appli2.stop_sequence.setdefault( len(command.process.namespec()) % 3, []).append(command.process)
        # call method and check result
        self.stopper.store_application_stop_sequence(appli1)
        # check application sequence in stopper planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                    2: ['sample_test_1:xclock']}}},
                             self.stopper.printable_planned_sequence())
        # call method a second time and check result
        self.stopper.store_application_stop_sequence(appli2)
        # check application sequence in stopper planned sequence
        self.assertDictEqual({0: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                    2: ['sample_test_1:xclock']},
                                  'sample_test_2': {0: ['sample_test_2:yeux_00', 'sample_test_2:yeux_01'],
                                                    1: ['sample_test_2:sleep']}}},
                             self.stopper.printable_planned_sequence())
    def test_process_job(self):
        """ Test the process_job method. """
        # get patches
        mocked_pusher = self.supvisors.zmq.pusher.send_stop_process
        # test with stopped process
        process = self._get_test_command('xlogo')
        jobs = []
        self.stopper.process_job(process, jobs)
        self.assertListEqual([], jobs)
        self.assertEqual(0, mocked_pusher.call_count)
        # test with running process
        process = self._get_test_command('xfontsel')
        jobs = []
        self.stopper.process_job(process, jobs)
        self.assertListEqual([process], jobs)
        self.assertEqual([call('10.0.0.1', 'sample_test_1:xfontsel')], mocked_pusher.call_args_list)

    def test_stop_process(self):
        """ Test the stop_process method. """
        # get any process
        xlogo_command = self._get_test_command('xlogo')
        # test failure
        with patch.object(self.stopper, 'process_job', return_value=False) as mocked_jobs:
            start_result = self.stopper.stop_process(xlogo_command.process)
            self.assertDictEqual({}, self.stopper.current_jobs)
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertTrue(start_result)

        # test success
        def success_job(*args, **kwargs):
            args[1].append(args[0])
            return True

        with patch.object(self.stopper, 'process_job', side_effect=success_job) as mocked_jobs:
            start_result = self.stopper.stop_process(xlogo_command.process)
            self.assertEqual(1, mocked_jobs.call_count)
            args1, _ = mocked_jobs.call_args
            self.assertDictEqual({'sample_test_1': [args1[0]]}, self.stopper.current_jobs)
            self.assertFalse(start_result)
            mocked_jobs.reset_mock()
            # get any other process
            yeux_command = self._get_test_command('yeux_00')
            # test that success complements current_jobs
            start_result = self.stopper.stop_process(yeux_command.process)
            self.assertEqual(1, mocked_jobs.call_count)
            args2, _ = mocked_jobs.call_args
            self.assertDictEqual({'sample_test_1': [args1[0]], 'sample_test_2': [args2[0]]},
                                 self.stopper.current_jobs)
            self.assertFalse(start_result)

    def test_stop_application(self):
        """ Test the stop_application method. """
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import ApplicationStates
        # create application start_sequence
        appli = ApplicationStatus('sample_test_1', self.supvisors.logger)
        for command in self.command_list:
            if command.process.application_name == 'sample_test_1':
                appli.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)

        # patch the starter.process_application_jobs
        def success_job(*args, **kwargs):
            args[1].append(args[0])

        with patch.object(self.stopper, 'process_job', side_effect=success_job) as mocked_jobs:
            # test start_application on a stopped application
            appli._state = ApplicationStates.STOPPED
            test_result = self.stopper.stop_application(appli)
            self.assertTrue(test_result)
            self.assertDictEqual({}, self.stopper.planned_sequence)
            self.assertDictEqual({}, self.stopper.planned_jobs)
            self.assertDictEqual({}, self.stopper.current_jobs)
            self.assertEqual(0, mocked_jobs.call_count)
            # test start_application on a stopped application
            appli._state = ApplicationStates.RUNNING
            test_result = self.stopper.stop_application(appli)
            self.assertFalse(test_result)
            # only planned jobs and not current jobs because of
            # process_application_jobs patch
            self.assertDictEqual({}, self.stopper.planned_sequence)
            self.assertDictEqual({'sample_test_1': {2: ['sample_test_1:xclock']}},
                                 self.stopper.printable_planned_jobs())
            self.assertDictEqual({'sample_test_1': ['sample_test_1:xfontsel', 'sample_test_1:xlogo']},
                                 self.stopper.printable_current_jobs())
            self.assertEqual(2, mocked_jobs.call_count)

    def test_stop_applications(self):
        """ Test the stop_applications method. """
        from supvisors.application import ApplicationStatus
        from supvisors.ttypes import ApplicationStates
        # create one running application with a start_sequence > 0
        appli = ApplicationStatus('sample_test_1', self.supvisors.logger)
        appli._state = ApplicationStates.RUNNING
        appli.rules.stop_sequence = 2
        self.supvisors.context.applications['sample_test_1'] = appli
        for command in self.command_list:
            if command.process.application_name == 'sample_test_1':
                appli.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        # create one stopped application
        appli = ApplicationStatus('sample_test_2', self.supvisors.logger)
        self.supvisors.context.applications['sample_test_2'] = appli
        # create one running application with a start_sequence == 0
        appli = ApplicationStatus('crash', self.supvisors.logger)
        appli._state = ApplicationStates.RUNNING
        appli.rules.stop_sequence = 0
        self.supvisors.context.applications['crash'] = appli
        for command in self.command_list:
            if command.process.application_name == 'crash':
                appli.stop_sequence.setdefault(len(command.process.namespec()) % 3, []).append(command.process)
        # call starter start_applications and check that only sample_test_2
        # is triggered
        with patch.object(self.stopper, 'process_application_jobs') as mocked_jobs:
            self.stopper.stop_applications()
            self.assertDictEqual({2: {'sample_test_1': {1: ['sample_test_1:xfontsel', 'sample_test_1:xlogo'],
                                                        2: ['sample_test_1:xclock']}}},
                                 self.stopper.printable_planned_sequence())
            self.assertDictEqual({'crash': {0: ['crash:late_segv'], 1: ['crash:segv']}},
                                 self.stopper.printable_planned_jobs())
            # current jobs is empty because of process_application_jobs mocking
            self.assertDictEqual({}, self.stopper.printable_current_jobs())
            self.assertEqual(1, mocked_jobs.call_count)
            self.assertEqual(call('crash'), mocked_jobs.call_args)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
