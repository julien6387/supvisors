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

from supervisors.tests.base import (DummyLogger, DummySupervisors,
    any_process_info, any_stopped_process_info, any_running_process_info,
    process_info_by_name, any_process_info_by_state)


class ProcessRulesTest(unittest.TestCase):
    """ Test case for the ProcessRulesStatus class of the process module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.logger = DummyLogger()

    def test_create(self):
        """ Test the values set at construction. """
        from supervisors.process import ProcessRules
        rules = ProcessRules(self.logger)
        self.assertIs(self.logger, rules.logger)
        self.assertListEqual(['*'], rules.addresses)
        self.assertEqual(0, rules.start_sequence)
        self.assertEqual(0, rules.stop_sequence)
        self.assertFalse(rules.required)
        self.assertFalse(rules.wait_exit)
        self.assertEqual(1, rules.expected_loading)

    def test_dependency_rules(self):
        """ Test the dependencies in process rules. """
        from supervisors.process import ProcessRules
        rules = ProcessRules(self.logger)
        # first test with no dependency issue
        rules.addresses = ['10.0.0.1', '10.0.0.2']
        rules.start_sequence = 1
        rules.stop_sequence = 1
        rules.required = True
        rules.wait_exit = False
        rules.expected_loading = 15
        # check dependencies
        rules.check_dependencies("dummy")
        # test that there is no difference
        self.assertListEqual(['10.0.0.1', '10.0.0.2'], rules.addresses)
        self.assertEqual(1, rules.start_sequence)
        self.assertEqual(1, rules.stop_sequence)
        self.assertTrue(rules.required)
        self.assertFalse(rules.wait_exit)
        self.assertEqual(15, rules.expected_loading)
        # second test with no dependency issue
        rules.addresses = ['10.0.0.2']
        rules.start_sequence = 0
        rules.stop_sequence = 1
        rules.required = False
        rules.wait_exit = True
        rules.expected_loading = 50
        # check dependencies
        rules.check_dependencies("dummy")
        # test that there is no difference
        self.assertListEqual(['10.0.0.2'], rules.addresses)
        self.assertEqual(0, rules.start_sequence)
        self.assertEqual(1, rules.stop_sequence)
        self.assertFalse(rules.required)
        self.assertTrue(rules.wait_exit)
        self.assertEqual(50, rules.expected_loading)
        # test with required and no sequence
        rules.addresses = ['10.0.0.1']
        rules.start_sequence = 0
        rules.stop_sequence = 0
        rules.required = True
        rules.wait_exit = False
        rules.expected_loading = 5
        # check dependencies
        rules.check_dependencies("dummy")
        # test that process is not required anymore
        self.assertListEqual(['10.0.0.1'], rules.addresses)
        self.assertEqual(0, rules.start_sequence)
        self.assertEqual(0, rules.stop_sequence)
        self.assertFalse(rules.required)
        self.assertFalse(rules.wait_exit)
        self.assertEqual(5, rules.expected_loading)
        # test empty addresses
        rules.addresses = []
        rules.start_sequence = 0
        rules.stop_sequence = 0
        rules.required = False
        rules.wait_exit = False
        rules.expected_loading = 0
        # check dependencies
        rules.check_dependencies("dummy")
        # test that all addresses are applicable
        self.assertListEqual(['*'], rules.addresses)
        self.assertEqual(0, rules.start_sequence)
        self.assertEqual(0, rules.stop_sequence)
        self.assertFalse(rules.required)
        self.assertFalse(rules.wait_exit)
        self.assertEqual(0, rules.expected_loading)

    def test_accept_extra_arguments(self):
        """ Test the possibility to add extra arguments when starting the process, iaw the process rules. """
        from supervisors.process import ProcessRules
        rules = ProcessRules(self.logger)
        # test all possibilities
        rules.required = False
        rules.start_sequence = 0
        self.assertTrue(rules.accept_extra_arguments())
        rules.required = True
        rules.start_sequence = 0
        self.assertFalse(rules.accept_extra_arguments())
        rules.required = False
        rules.start_sequence = 1
        self.assertFalse(rules.accept_extra_arguments())
        rules.required = True
        rules.start_sequence = 1
        self.assertFalse(rules.accept_extra_arguments())


class ProcessTest(unittest.TestCase):
    """ Test case for the ProcessStatus class of the process module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supervisors = DummySupervisors()

    def test_create(self):
        """ Test the values set at construction. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessRules, ProcessStatus
        # test with stopped process
        info = any_stopped_process_info()
        process = ProcessStatus('10.0.0.1', info, self.supervisors)
        # check application default attributes
        self.assertIs(self.supervisors, process.supervisors)
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
        process = ProcessStatus('10.0.0.1', info, self.supervisors)
        # check application default attributes
        self.assertIs(self.supervisors, process.supervisors)
        self.assertEqual(info['group'], process.application_name)
        self.assertEqual(info['name'], process.process_name)
        self.assertEqual(info['state'], process.state)
        self.assertTrue(process.expected_exit)
        self.assertEqual(info['now'], process.last_event_time)
        self.assertFalse(process.mark_for_restart)
        self.assertFalse(process.ignore_wait_exit)
        self.assertSetEqual({'10.0.0.1'}, process.addresses)
        self.assertListEqual(['10.0.0.1'], process.infos.keys())
        process_info = process.infos['10.0.0.1']
        self.assertEqual(process_info['event_time'], process_info['now'])
        self.assertLessEqual(0, process_info['pid'])
        # test with one STOPPING
        info = any_process_info_by_state(ProcessStates.STOPPING)
        process = ProcessStatus('10.0.0.1', info.copy(), self.supervisors)
        # check application default attributes
        self.assertIs(self.supervisors, process.supervisors)
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
        self.assertLessEqual(0, process_info['pid'])
        # rules part (independent from state)
        self.assertDictEqual(ProcessRules(self.supervisors.logger).__dict__, process.rules.__dict__)

    def test_namespec(self):
        """ Test of the process namspec. """
        from supervisors.process import ProcessStatus
        # test namespec when group and name are different
        info = process_info_by_name('segv')
        process = ProcessStatus('10.0.0.1', info, self.supervisors)
        self.assertEqual('crash:segv', process.namespec())
        # test namespec when group and name are identical
        info = process_info_by_name('firefox')
        process = ProcessStatus('10.0.0.1', info, self.supervisors)
        self.assertEqual('firefox', process.namespec())

    def test_stopped_running(self):
        """ Test the stopped / running status. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # test with STOPPED process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.supervisors)
        self.assertTrue(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        # test with BACKOFF process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.BACKOFF), self.supervisors)
        self.assertFalse(process.stopped())
        self.assertTrue(process.running())
        self.assertTrue(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with RUNNING process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.RUNNING), self.supervisors)
        self.assertFalse(process.stopped())
        self.assertTrue(process.running())
        self.assertTrue(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertTrue(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with STOPPING process
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPING), self.supervisors)
        self.assertFalse(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))

    def test_conflicting(self):
        """ Test the process conflicting rules. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # when there is only one STOPPED process info, there is no conflict
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.supervisors)
        self.assertFalse(process.conflicting())
        # the addition of a running address, still no conflict
        process.addresses.add('10.0.0.2')
        self.assertFalse(process.conflicting())
        # the addition of a new running address raises a conflict
        process.addresses.add('10.0.0.4')
        self.assertTrue(process.conflicting())
        # remove the first running address to solve the conflict
        process.addresses.remove('10.0.0.2')
        self.assertFalse(process.conflicting())

    def test_serialization(self):
        """ Test the serialization of the ProcessStatus. """
        import pickle
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # test with a STOPPED process
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus('10.0.0.1', info, self.supervisors)
        json = process.to_json()
        self.assertDictEqual(json, {'application_name': info['group'], 'process_name': info['name'],
            'statecode': 0, 'statename': 'STOPPED',
            'expected_exit': not info['spawnerr'], 'last_event_time': process.last_event_time, 'addresses': []})
        # test that returned structure is serializable using pickle
        serial = pickle.dumps(json)
        after_json = pickle.loads(serial)
        self.assertDictEqual(json, after_json)

    def test_add_info(self):
        """ Test the addition of a process info into the ProcessStatus. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # ProcessStatus constructor uses add_info
        info = any_process_info_by_state(ProcessStates.STOPPING)
        self.assertNotIn('event_time', info)
        self.assertNotIn('local_time', info)
        self.assertNotIn('uptime', info)
        process = ProcessStatus('10.0.0.1', info, self.supervisors)
        # check contents
        self.assertEqual(1, len(process.infos))
        self.assertIs(info, process.infos['10.0.0.1'])
        self.assertIsNotNone(process.last_event_time)
        last_event_time = process.last_event_time
        self.assertIn('event_time', info)
        self.assertIn('local_time', info)
        self.assertIn('uptime', info)
        self.assertEqual(last_event_time, info['event_time'])
        self.assertEqual(last_event_time, info['now'])
        self.assertEqual(info['now'] - info['start'], info['uptime'])
        self.assertFalse(process.addresses)
        self.assertEqual(ProcessStates.STOPPING, process.state)
        self.assertTrue(process.expected_exit)
        # replace with an EXITED process info
        info = any_process_info_by_state(ProcessStates.EXITED)
        process.add_info('10.0.0.1', info)
        # check contents
        self.assertEqual(1, len(process.infos))
        self.assertIs(info, process.infos['10.0.0.1'])
        self.assertIsNotNone(process.last_event_time)
        self.assertNotEqual(last_event_time, process.last_event_time)
        last_event_time = process.last_event_time
        self.assertIn('event_time', info)
        self.assertIn('local_time', info)
        self.assertIn('uptime', info)
        self.assertEqual(last_event_time, info['event_time'])
        self.assertEqual(last_event_time, info['now'])
        self.assertFalse(process.addresses)
        self.assertEqual(ProcessStates.EXITED, process.state)
        self.assertTrue(process.expected_exit)
        # add a RUNNING process info
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.RUNNING))

    def test_update_info(self):
        """ Test the update of the ProcessStatus upon reception of a process event. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # add a STOPPED process infos into a process status
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.supervisors)
        self.assertEqual(ProcessStates.STOPPED, process.infos['10.0.0.1']['state'])
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertFalse(process.addresses)
        local_time = process.infos['10.0.0.1']['local_time']
        # update with a STARTING event
        process.update_info('10.0.0.1', {'state': ProcessStates.STARTING, 'now': 10})
        # check changes
        info = process.infos['10.0.0.1']
        self.assertEqual(ProcessStates.STARTING, info['state'])
        self.assertEqual(ProcessStates.STARTING, process.state)
        self.assertSetEqual({'10.0.0.1'}, process.addresses)
        self.assertEqual(10, process.last_event_time)
        self.assertEqual(10, info['event_time'])
        self.assertEqual(10, info['now'])
        self.assertGreaterEqual(info['local_time'], local_time)
        local_time = info['local_time']
        self.assertEqual(10, info['start'])
        self.assertEqual(0, info['stop'])
        self.assertEqual(0, info['uptime'])
        # update with a RUNNING event
        process.update_info('10.0.0.1', {'state': ProcessStates.RUNNING, 'now': 15, 'pid': 1234})
        # check changes
        self.assertEqual(ProcessStates.RUNNING, info['state'])
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertSetEqual({'10.0.0.1'}, process.addresses)
        self.assertEqual(15, process.last_event_time)
        self.assertEqual(1234, info['pid'])
        self.assertEqual(15, info['event_time'])
        self.assertEqual(15, info['now'])
        self.assertGreaterEqual(info['local_time'], local_time)
        local_time = info['local_time']
        self.assertEqual(10, info['start'])
        self.assertEqual(0, info['stop'])
        self.assertEqual(5, info['uptime'])
        # add a new STOPPED process info and update with STARTING / RUNNING events
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
        process.update_info('10.0.0.2', {'state': ProcessStates.STARTING, 'now': 20})
        process.update_info('10.0.0.2', {'state': ProcessStates.RUNNING, 'now': 25, 'pid': 4321})
        # check state and addresses
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertSetEqual({'10.0.0.1', '10.0.0.2'}, process.addresses)
        self.assertEqual(25, process.last_event_time)
        # update with an EXITED event
        process.update_info('10.0.0.1', {'state': ProcessStates.EXITED, 'now': 30, 'expected': False})
        # check changes
        self.assertEqual(ProcessStates.EXITED, info['state'])
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertSetEqual({'10.0.0.2'}, process.addresses)
        self.assertEqual(30, process.last_event_time)
        self.assertEqual(0, info['pid'])
        self.assertEqual(30, info['event_time'])
        self.assertEqual(30, info['now'])
        self.assertGreaterEqual(info['local_time'], local_time)
        self.assertEqual(10, info['start'])
        self.assertEqual(30, info['stop'])
        self.assertEqual(0, info['uptime'])
        self.assertFalse(info['expected'])
        # update with an STOPPING event
        info = process.infos['10.0.0.2']
        local_time = info['local_time']
        process.update_info('10.0.0.2', {'state': ProcessStates.STOPPING, 'now': 35})
        # check changes
        self.assertEqual(ProcessStates.STOPPING, info['state'])
        self.assertEqual(ProcessStates.STOPPING, process.state)
        self.assertSetEqual({'10.0.0.2'}, process.addresses)
        self.assertEqual(35, process.last_event_time)
        self.assertEqual(4321, info['pid'])
        self.assertEqual(35, info['event_time'])
        self.assertEqual(35, info['now'])
        self.assertGreaterEqual(info['local_time'], local_time)
        local_time = info['local_time']
        self.assertEqual(20, info['start'])
        self.assertEqual(0, info['stop'])
        self.assertEqual(15, info['uptime'])
        self.assertTrue(info['expected'])
       # update with an STOPPED event
        process.update_info('10.0.0.2', {'state': ProcessStates.STOPPED, 'now': 40})
        # check changes
        self.assertEqual(ProcessStates.STOPPED, info['state'])
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertFalse(process.addresses)
        self.assertEqual(40, process.last_event_time)
        self.assertEqual(0, info['pid'])
        self.assertEqual(40, info['event_time'])
        self.assertEqual(40, info['now'])
        self.assertGreaterEqual(info['local_time'], local_time)
        self.assertEqual(20, info['start'])
        self.assertEqual(40, info['stop'])
        self.assertEqual(0, info['uptime'])
        self.assertTrue(info['expected'])

    def test_update_times(self):
        """ Test the update of the time entries for a process info belonging to a ProcessStatus. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # add 2 process infos into a process status
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPING), self.supervisors)
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
        # get their time values
        now_1 = process.infos['10.0.0.1']['now']
        local_1 = process.infos['10.0.0.1']['local_time']
        uptime_1 = process.infos['10.0.0.1']['uptime']
        now_2 = process.infos['10.0.0.2']['now']
        local_2 = process.infos['10.0.0.2']['local_time']
        # update times on address 2
        process.update_times('10.0.0.2', now_2 + 10, local_2 + 10)
        # check that nothing changed for address 1
        self.assertEqual(now_1, process.infos['10.0.0.1']['now'])
        self.assertEqual(local_1, process.infos['10.0.0.1']['local_time'])
        self.assertEqual(uptime_1, process.infos['10.0.0.1']['uptime'])
        # check that times changed for address 2 (uptime excepted)
        self.assertEqual(now_2 + 10, process.infos['10.0.0.2']['now'])
        self.assertEqual(local_2 + 10, process.infos['10.0.0.2']['local_time'])
        self.assertEqual(0, process.infos['10.0.0.2']['uptime'])
        # update times on address 1
        process.update_times('10.0.0.1', now_1 + 20, local_1 + 19)
        # check that times changed for address 1 (including uptime)
        self.assertEqual(now_1 + 20, process.infos['10.0.0.1']['now'])
        self.assertEqual(local_1 + 19, process.infos['10.0.0.1']['local_time'])
        self.assertEqual(uptime_1 + 20, process.infos['10.0.0.1']['uptime'])
        # check that nothing changed for address 2
        self.assertEqual(now_2 + 10, process.infos['10.0.0.2']['now'])
        self.assertEqual(local_2 + 10, process.infos['10.0.0.2']['local_time'])
        self.assertEqual(0, process.infos['10.0.0.2']['uptime'])

    def test_update_single_times(self):
        """ Test the update of time entries in a Process info dictionary. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # check times on a RUNNING process info
        info = any_process_info_by_state(ProcessStates.RUNNING)
        ProcessStatus.update_single_times(info, info['start'] + 10, 100)
        self.assertEqual(info['start'] + 10, info['now'])
        self.assertEqual(100, info['local_time'])
        self.assertEqual(10, info['uptime'])
        # check times on a STOPPED-like process info
        info = any_stopped_process_info()
        ProcessStatus.update_single_times(info, 10, 100)
        self.assertEqual(10, info['now'])
        self.assertEqual(100, info['local_time'])
        self.assertEqual(0, info['uptime'])

    def test_invalidate_address(self):
        """ Test the invalidation of addresses. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # create conflict directly with 3 process info
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.BACKOFF), self.supervisors)
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.RUNNING))
        process.add_info('10.0.0.3', any_process_info_by_state(ProcessStates.STARTING))
        # check the conflict
        self.assertTrue(process.conflicting())
        self.assertEqual(ProcessStates.RUNNING, process.state)
        # invalidate RUNNING one
        process.invalidate_address('10.0.0.2')
        # check UNKNOWN
        self.assertEqual(ProcessStates.UNKNOWN, process.infos['10.0.0.2']['state'])
        # check the conflict
        self.assertTrue(process.conflicting())
        # check new synthetic state
        self.assertEqual(ProcessStates.BACKOFF, process.state)
        # invalidate BACKOFF one
        process.invalidate_address('10.0.0.1')
        # check UNKNOWN
        self.assertEqual(ProcessStates.UNKNOWN, process.infos['10.0.0.1']['state'])
        # check 1 address: no conflict
        self.assertFalse(process.conflicting())
        # check state (running process)
        self.assertEqual(ProcessStates.STARTING, process.state)
        # invalidate STARTING one
        process.invalidate_address('10.0.0.3')
        # check UNKNOWN
        self.assertEqual(ProcessStates.UNKNOWN, process.infos['10.0.0.3']['state'])
        # check 0 address: no conflict
        self.assertFalse(process.conflicting())
        # check state FATAL
        self.assertEqual(ProcessStates.FATAL, process.state)
        # check mark_for_restart
        self.assertTrue(process.mark_for_restart)
        # unset mark_for_restart
        process.mark_for_restart = False
        # add one STOPPING
        process.add_info('10.0.0.4', any_process_info_by_state(ProcessStates.STOPPING))
        # check state STOPPING
        self.assertEqual(ProcessStates.STOPPING, process.state)
        # invalidate STOPPING one
        process.invalidate_address('10.0.0.4')
        # check UNKNOWN
        self.assertEqual(ProcessStates.UNKNOWN, process.infos['10.0.0.4']['state'])
        # check state STOPPED
        self.assertEqual(ProcessStates.STOPPED, process.state)

    def test_update_status(self):
        """ Test the update of state and running addresses. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # update_status is called in the construction
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.supervisors)
        self.assertFalse(process.addresses)
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertTrue(process.expected_exit)
        # replace with an EXITED process info
        process.infos['10.0.0.1'] = any_process_info_by_state(ProcessStates.EXITED)
        process.update_status('10.0.0.1', ProcessStates.EXITED, False)
        self.assertFalse(process.addresses)
        self.assertEqual(ProcessStates.EXITED, process.state)
        self.assertFalse(process.expected_exit)
        # add a STARTING process info
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
        process.update_status('10.0.0.2', ProcessStates.STARTING, True)
        self.assertSetEqual({'10.0.0.2'}, process.addresses)
        self.assertEqual(ProcessStates.STARTING, process.state)
        self.assertTrue(process.expected_exit)
        # add a BACKOFF process info
        process.infos['10.0.0.3'] = any_process_info_by_state(ProcessStates.BACKOFF)
        process.update_status('10.0.0.3', ProcessStates.STARTING, True)
        self.assertSetEqual({'10.0.0.3', '10.0.0.2'}, process.addresses)
        self.assertEqual(ProcessStates.BACKOFF, process.state)
        self.assertTrue(process.expected_exit)
        # replace STARTING process info with RUNNING
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
        process.update_status('10.0.0.2', ProcessStates.RUNNING, True)
        self.assertSetEqual({'10.0.0.3', '10.0.0.2'}, process.addresses)
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertTrue(process.expected_exit)
        # replace BACKOFF process info with FATAL
        process.infos['10.0.0.3'] = any_process_info_by_state(ProcessStates.FATAL)
        process.update_status('10.0.0.3', ProcessStates.FATAL, False)
        self.assertSetEqual({'10.0.0.2'}, process.addresses)
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertTrue(process.expected_exit)
        # replace RUNNING process info with STOPPED
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.STOPPED)
        process.update_status('10.0.0.2', ProcessStates.STOPPED, False)
        self.assertFalse(process.addresses)
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertFalse(process.expected_exit)

    def test_evaluate_conflict(self):
        """ Test the determination of a synthetic state in case of conflict. """
        from supervisor.states import ProcessStates
        from supervisors.process import ProcessStatus
        # when there is only one STOPPED process info, there is no conflict
        process = ProcessStatus('10.0.0.1', any_process_info_by_state(ProcessStates.STOPPED), self.supervisors)
        self.assertFalse(process.evaluate_conflict())
        self.assertEqual(ProcessStates.STOPPED, process.state)
        # the addition of one RUNNING process info does not raise any conflict
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
        process.addresses = {'10.0.0.2'}
        self.assertFalse(process.evaluate_conflict())
        # the addition of one STARTING process raises a conflict
        process.infos['10.0.0.3'] = any_process_info_by_state(ProcessStates.STARTING)
        process.addresses.add('10.0.0.3')
        self.assertTrue(process.evaluate_conflict())
        self.assertEqual(ProcessStates.RUNNING, process.state)
        # replace the RUNNING process info with a BACKOFF process info
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.BACKOFF)
        self.assertTrue(process.evaluate_conflict())
        self.assertEqual(ProcessStates.BACKOFF, process.state)
        # replace the BACKOFF process info with a STARTING process info
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
        self.assertTrue(process.evaluate_conflict())
        self.assertEqual(ProcessStates.STARTING, process.state)
        # replace the STARTING process info with an EXITED process info
        process.infos['10.0.0.2'] = any_process_info_by_state(ProcessStates.EXITED)
        process.addresses.remove('10.0.0.2')
        self.assertFalse(process.evaluate_conflict())
        self.assertEqual(ProcessStates.STARTING, process.state)

    def test_filter(self):
        """ Test the filtering of unused entries into process info dictionary. """
        from supervisors.process import ProcessStatus
        info = any_process_info()
        all_keys = info.keys()
        removed_keys = ['statename', 'description', 'stderr_logfile', 'stdout_logfile', 'logfile', 'exitstatus']
        kept_keys = filter(lambda x: x not in removed_keys, all_keys)
        # check that keys to be filtered are there
        for key in removed_keys:
            self.assertIn(key, all_keys)
        # check filtering
        ProcessStatus.filter(info)
        info_keys = info.keys()
        # check that keys to be filtered have been removed
        for key in removed_keys:
            self.assertNotIn(key, info_keys)
        for key in kept_keys:
            self.assertIn(key, info_keys)

    def test_running_state(self):
        """ Test the choice of a single state among a list of states. """
        from supervisor.states import ProcessStates, STOPPED_STATES, RUNNING_STATES
        from supervisors.process import ProcessStatus
        # check running states with several combinations
        self.assertEqual(ProcessStates.UNKNOWN, ProcessStatus.running_state(STOPPED_STATES))
        self.assertEqual(ProcessStates.UNKNOWN, ProcessStatus.running_state([ProcessStates.STOPPING]))
        self.assertEqual(ProcessStates.RUNNING, ProcessStatus.running_state(RUNNING_STATES))
        self.assertEqual(ProcessStates.BACKOFF, ProcessStatus.running_state([ProcessStates.STARTING, ProcessStates.BACKOFF]))
        self.assertEqual(ProcessStates.STARTING, ProcessStatus.running_state([ProcessStates.STARTING]))
        self.assertEqual(ProcessStates.RUNNING, ProcessStatus.running_state([ProcessStates.STOPPING] + list(RUNNING_STATES) + list(STOPPED_STATES)))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

