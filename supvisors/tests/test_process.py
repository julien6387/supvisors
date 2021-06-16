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

from supervisor.states import ProcessStates, _process_states_by_code
from unittest.mock import call, patch

from supvisors.tests.base import (MockedSupvisors,
                                  any_process_info,
                                  any_stopped_process_info,
                                  process_info_by_name,
                                  any_process_info_by_state)


class ProcessRulesTest(unittest.TestCase):
    """ Test case for the ProcessRulesStatus class of the process module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()

    def test_create(self):
        """ Test the values set at construction. """
        from supvisors.process import ProcessRules
        from supvisors.ttypes import RunningFailureStrategies
        rules = ProcessRules(self.supvisors)
        self.assertIs(self.supvisors, rules.supvisors)
        self.assertListEqual(['*'], rules.node_names)
        self.assertEqual(0, rules.start_sequence)
        self.assertEqual(0, rules.stop_sequence)
        self.assertFalse(rules.required)
        self.assertFalse(rules.wait_exit)
        self.assertEqual(1, rules.expected_load)
        self.assertEqual(RunningFailureStrategies.CONTINUE, rules.running_failure_strategy)

    def test_str(self):
        """ Test the string output. """
        from supvisors.process import ProcessRules
        rules = ProcessRules(self.supvisors)
        self.assertEqual("node_names=['*'] hash_node_names=None start_sequence=0 stop_sequence=0 required=False"
                         " wait_exit=False expected_load=1 running_failure_strategy=CONTINUE", str(rules))

    def test_serial(self):
        """ Test the serialization of the ProcessRules object. """
        from supvisors.process import ProcessRules
        rules = ProcessRules(self.supvisors)
        self.assertDictEqual({'addresses': ['*'],
                              'start_sequence': 0, 'stop_sequence': 0,
                              'required': False, 'wait_exit': False, 'expected_loading': 1,
                              'running_failure_strategy': 'CONTINUE'}, rules.serial())

    def test_check_start_sequence(self):
        """ Test the dependencies in process rules. """
        from supvisors.process import ProcessRules
        rules = ProcessRules(self.supvisors)
        # 1. test with not required and no start sequence
        rules.start_sequence = 0
        rules.required = False
        # call check dependencies
        rules.check_dependencies('dummy')
        # check rules unchanged 
        self.assertEqual(0, rules.start_sequence)
        self.assertFalse(rules.required)
        # 2. test with required and no start sequence
        rules.start_sequence = 0
        rules.required = True
        # check dependencies
        rules.check_dependencies('dummy')
        # check required has been changed
        self.assertEqual(0, rules.start_sequence)
        self.assertFalse(rules.required)
        # 3. test with not required and start sequence
        rules.start_sequence = 1
        rules.required = False
        # check dependencies
        rules.check_dependencies('dummy')
        # check rules unchanged 
        self.assertEqual(1, rules.start_sequence)
        self.assertFalse(rules.required)
        # 4. test with required and start sequence
        rules.start_sequence = 1
        rules.required = True
        # check dependencies
        rules.check_dependencies('dummy')
        # check rules unchanged 
        self.assertEqual(1, rules.start_sequence)
        self.assertTrue(rules.required)

    def test_check_autorestart(self):
        """ Test the dependency related to running failure strategy in process rules.
        Done in a separate test as it impacts the supervisor internal model. """
        from supvisors.process import ProcessRules
        from supvisors.ttypes import RunningFailureStrategies
        rules = ProcessRules(self.supvisors)
        # test that only the CONTINUE strategy keeps the autorestart
        mocked_disable = self.supvisors.info_source.disable_autorestart
        for strategy in RunningFailureStrategies:
            rules.running_failure_strategy = strategy
            rules.check_autorestart('dummy_process_1')
            if strategy == RunningFailureStrategies.CONTINUE:
                self.assertEqual(0, mocked_disable.call_count)
            else:
                self.assertEqual([call('dummy_process_1')], mocked_disable.call_args_list)
                mocked_disable.reset_mock()

    def test_check_hash_nodes(self):
        """ Test the resolution of addresses when hash_address is set. """
        from supvisors.process import ProcessRules
        # create rules and check initial attributes
        rules = ProcessRules(self.supvisors)
        self.assertEqual(['*'], rules.node_names)
        self.assertIsNone(rules.hash_node_names)
        # in mocked supvisors, xclock has a procnumber of 2
        # 1. test with unknown namespec
        rules.check_hash_nodes('sample_test_1:xfontsel')
        # node_names is unchanged
        self.assertListEqual(['*'], rules.node_names)
        # 2. update rules to test '#' with all nodes available
        rules.hash_node_names = ['*']
        rules.node_names = []
        # address '10.0.0.2' has an index of 2 in address_mapper
        rules.check_hash_nodes('sample_test_1:xclock')
        self.assertListEqual(['10.0.0.2'], rules.node_names)
        # 3. update rules to test '#' with a subset of nodes available
        rules.hash_node_names = ['10.0.0.0', '10.0.0.3', '10.0.0.5']
        rules.node_names = []
        # here, at index 2 of this list, '10.0.0.5' can be found
        rules.check_hash_nodes('sample_test_1:xclock')
        self.assertListEqual(['10.0.0.5'], rules.node_names)
        # 4. test the case where procnumber is greater than the subset list of nodes available
        rules.hash_node_names = ['10.0.0.1']
        rules.node_names = []
        rules.check_hash_nodes('sample_test_1:xclock')
        self.assertListEqual([], rules.node_names)

    @patch('supvisors.process.ProcessRules.check_hash_nodes')
    @patch('supvisors.process.ProcessRules.check_autorestart')
    @patch('supvisors.process.ProcessRules.check_start_sequence')
    def test_check_dependencies(self, mocked_start, mocked_auto, mocked_hash):
        """ Test the dependencies in process rules. """
        from supvisors.process import ProcessRules
        rules = ProcessRules(self.supvisors)
        # test with no hash
        rules.hash_node_names = []
        # check dependencies
        rules.check_dependencies('dummy')
        # test calls
        self.assertEqual([call('dummy')], mocked_start.call_args_list)
        self.assertEqual([call('dummy')], mocked_auto.call_args_list)
        self.assertFalse(mocked_hash.called)
        # reset mocks
        mocked_start.reset_mock()
        mocked_auto.reset_mock()
        # test with hash
        rules.hash_node_names = ['*']
        # check dependencies
        rules.check_dependencies('dummy')
        # test calls
        self.assertEqual([call('dummy')], mocked_start.call_args_list)
        self.assertEqual([call('dummy')], mocked_auto.call_args_list)
        self.assertEqual([call('dummy')], mocked_hash.call_args_list)


class ProcessTest(unittest.TestCase):
    """ Test case for the ProcessStatus class of the process module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()

    def test_create(self):
        """ Test the values set at construction. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessRules, ProcessStatus
        info = any_stopped_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        # check application default attributes
        self.assertIs(self.supvisors, process.supvisors)
        self.assertEqual(info['group'], process.application_name)
        self.assertEqual(info['name'], process.process_name)
        self.assertEqual(ProcessStates.UNKNOWN, process.state)
        self.assertTrue(process.expected_exit)
        self.assertEqual(0, process.last_event_time)
        self.assertEqual('', process.extra_args)
        self.assertEqual(set(), process.running_nodes)
        self.assertEqual({}, process.info_map)
        # rules part
        self.assertDictEqual(ProcessRules(self.supvisors).__dict__,
                             process.rules.__dict__)

    def test_namespec(self):
        """ Test of the process namspec. """
        from supvisors.process import ProcessStatus
        # test namespec when group and name are different
        info = process_info_by_name('segv')
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        self.assertEqual('crash:segv', process.namespec())
        # test namespec when group and name are identical
        info = process_info_by_name('firefox')
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        self.assertEqual('firefox', process.namespec())

    def test_possible_nodes(self):
        """ Test the possible_nodes method. """
        from supvisors.process import ProcessStatus
        info = any_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.2', info)
        process.add_info('10.0.0.4', info)
        # default node_names is '*' in process rules
        self.assertEqual(['10.0.0.2', '10.0.0.4'], process.possible_nodes())
        # set a subset of node_names in process rules so that there's no intersection with received status
        process.rules.node_names = ['10.0.0.1', '10.0.0.3']
        self.assertEqual([], process.possible_nodes())
        # increase received status
        process.add_info('10.0.0.3', info)
        self.assertEqual(['10.0.0.3'], process.possible_nodes())
        # reset rules
        process.rules.node_names = ['*']
        self.assertEqual(['10.0.0.2', '10.0.0.3', '10.0.0.4'], process.possible_nodes())
        # test with full status and all nodes in rules
        for node_name in self.supvisors.address_mapper.node_names:
            process.add_info(node_name, info)
        self.assertEqual(self.supvisors.address_mapper.node_names, process.possible_nodes())
        # restrict again nodes in rules
        process.rules.node_names = ['10.0.0.5']
        self.assertEqual(['10.0.0.5'], process.possible_nodes())

    def test_stopped_running(self):
        """ Test the stopped / running / crashed status. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # test with STOPPED process
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertTrue(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.crashed())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        # test with BACKOFF process
        info = any_process_info_by_state(ProcessStates.BACKOFF)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertFalse(process.stopped())
        self.assertTrue(process.running())
        self.assertFalse(process.crashed())
        self.assertTrue(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with RUNNING process
        info = any_process_info_by_state(ProcessStates.RUNNING)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertFalse(process.stopped())
        self.assertTrue(process.running())
        self.assertFalse(process.crashed())
        self.assertTrue(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertTrue(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with STOPPING process
        info = any_process_info_by_state(ProcessStates.STOPPING)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertFalse(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.crashed())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with FATAL process
        info = any_process_info_by_state(ProcessStates.FATAL)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertTrue(process.stopped())
        self.assertFalse(process.running())
        self.assertTrue(process.crashed())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with EXITED and expected_exit
        info = any_process_info_by_state(ProcessStates.EXITED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        process.expected_exit = True
        self.assertTrue(process.stopped())
        self.assertFalse(process.running())
        self.assertFalse(process.crashed())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))
        # test with EXITED and unexpected_exit
        process.expected_exit = False
        self.assertTrue(process.stopped())
        self.assertFalse(process.running())
        self.assertTrue(process.crashed())
        self.assertFalse(process.running_on('10.0.0.1'))
        self.assertFalse(process.running_on('10.0.0.2'))
        self.assertFalse(process.pid_running_on('10.0.0.1'))
        self.assertFalse(process.pid_running_on('10.0.0.2'))

    def test_conflicting(self):
        """ Test the process conflicting rules. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # when there is only one STOPPED process info, there is no conflict
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertFalse(process.conflicting())
        # the addition of a running address, still no conflict
        process.running_nodes.add('10.0.0.2')
        self.assertFalse(process.conflicting())
        # the addition of a new running address raises a conflict
        process.running_nodes.add('10.0.0.4')
        self.assertTrue(process.conflicting())
        # remove the first running address to solve the conflict
        process.running_nodes.remove('10.0.0.2')
        self.assertFalse(process.conflicting())

    def test_serialization(self):
        """ Test the serialization of the ProcessStatus. """
        import pickle
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # test with a STOPPED process
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        serialized = process.serial()
        self.assertDictEqual({'application_name': info['group'],
                              'process_name': info['name'],
                              'statecode': 0,
                              'statename': 'STOPPED',
                              'expected_exit': info['expected'],
                              'last_event_time': process.last_event_time,
                              'addresses': [],
                              'extra_args': ''},
                             serialized)
        # test that returned structure is serializable using pickle
        dumped = pickle.dumps(serialized)
        loaded = pickle.loads(dumped)
        self.assertDictEqual(serialized, loaded)

    def test_add_info(self):
        """ Test the addition of a process info into the ProcessStatus. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # get a process info and complement extra_args
        info = process_info_by_name('xclock')
        info['extra_args'] = '-x dummy'
        self.assertNotIn('uptime', info)
        # 1. create ProcessStatus instance
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.extra_args = 'something else'
        process.add_info('10.0.0.1', info)
        # check last event info
        self.assertGreater(process.last_event_time, 0)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check contents
        self.assertEqual(1, len(process.info_map))
        self.assertIs(info, process.info_map['10.0.0.1'])
        self.assertEqual(info['now'] - info['start'], info['uptime'])
        self.assertFalse(process.running_nodes)
        self.assertEqual(ProcessStates.STOPPING, process.state)
        self.assertTrue(process.expected_exit)
        # extra_args are reset when using add_info
        self.assertEqual('', process.extra_args)
        self.assertEqual('', info['extra_args'])
        # 2. replace with an EXITED process info
        info = any_process_info_by_state(ProcessStates.EXITED)
        process.add_info('10.0.0.1', info)
        # check last event info
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check contents
        self.assertEqual(1, len(process.info_map))
        self.assertIs(info, process.info_map['10.0.0.1'])
        self.assertEqual(0, info['uptime'])
        self.assertFalse(process.running_nodes)
        self.assertEqual(ProcessStates.EXITED, process.state)
        self.assertTrue(process.expected_exit)
        # update rules to test '#'
        process.rules.hash_addresses = ['*']
        # 3. add a RUNNING process info
        info = any_process_info_by_state(ProcessStates.RUNNING)
        process.add_info('10.0.0.2', info)
        # check last event info
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        self.assertEqual(info['local_time'], last_event_time)
        # check contents
        self.assertEqual(2, len(process.info_map))
        self.assertIs(info, process.info_map['10.0.0.2'])
        self.assertEqual(info['now'] - info['start'], info['uptime'])
        self.assertEqual({'10.0.0.2'}, process.running_nodes)
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertTrue(process.expected_exit)

    def test_update_info(self):
        """ Test the update of the ProcessStatus upon reception of a process event. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # 1. add a STOPPED process infos into a process status
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        # test last event info stored
        self.assertGreater(process.last_event_time, 0)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check changes on status
        self.assertEqual(ProcessStates.STOPPED, process.info_map['10.0.0.1']['state'])
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertEqual('', process.extra_args)
        self.assertFalse(process.running_nodes)
        # 2. update with a STARTING event on an unknown address
        process.update_info('10.0.0.2', {'state': ProcessStates.STARTING, 'now': 10})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check no change on other status
        info = process.info_map['10.0.0.1']
        self.assertEqual(ProcessStates.STOPPED, info['state'])
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertEqual('', process.extra_args)
        self.assertFalse(process.running_nodes)
        # 3. update with a STARTING event
        process.update_info('10.0.0.1', {'state': ProcessStates.STARTING,
                                         'now': 10,
                                         'extra_args': '-x dummy'})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check changes on status
        info = process.info_map['10.0.0.1']
        self.assertEqual(ProcessStates.STARTING, info['state'])
        self.assertEqual(ProcessStates.STARTING, process.state)
        self.assertEqual('-x dummy', process.extra_args)
        self.assertSetEqual({'10.0.0.1'}, process.running_nodes)
        self.assertEqual(10, info['now'])
        self.assertEqual(10, info['start'])
        self.assertEqual(0, info['uptime'])
        # 4. update with a RUNNING event
        process.update_info('10.0.0.1', {'state': ProcessStates.RUNNING,
                                         'now': 15,
                                         'pid': 1234,
                                         'extra_args': '-z another'})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check changes
        self.assertEqual(ProcessStates.RUNNING, info['state'])
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertSetEqual({'10.0.0.1'}, process.running_nodes)
        self.assertEqual('-z another', process.extra_args)
        self.assertEqual(1234, info['pid'])
        self.assertEqual(15, info['now'])
        self.assertEqual(10, info['start'])
        self.assertEqual(5, info['uptime'])
        # 5.a add a new STOPPED process info
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # extra_args has been reset
        self.assertEqual('', process.extra_args)
        # 5.b update with STARTING / RUNNING events
        process.update_info('10.0.0.2', {'state': ProcessStates.STARTING,
                                         'now': 20,
                                         'extra_args': '-x dummy'})
        process.update_info('10.0.0.2', {'state': ProcessStates.RUNNING,
                                         'now': 25,
                                         'pid': 4321,
                                         'extra_args': ''})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check state and addresses
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertEqual('', process.extra_args)
        self.assertSetEqual({'10.0.0.1', '10.0.0.2'}, process.running_nodes)
        # 6. update with an EXITED event
        process.update_info('10.0.0.1', {'state': ProcessStates.EXITED,
                                         'now': 30,
                                         'expected': False,
                                         'extra_args': ''})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check changes
        self.assertEqual(ProcessStates.EXITED, info['state'])
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertEqual('', process.extra_args)
        self.assertSetEqual({'10.0.0.2'}, process.running_nodes)
        self.assertEqual(1234, info['pid'])
        self.assertEqual(30, info['now'])
        self.assertEqual(10, info['start'])
        self.assertEqual(0, info['uptime'])
        self.assertFalse(info['expected'])
        # 7. update with an STOPPING event
        info = process.info_map['10.0.0.2']
        process.update_info('10.0.0.2', {'state': ProcessStates.STOPPING,
                                         'now': 35,
                                         'extra_args': ''})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check changes
        self.assertEqual(ProcessStates.STOPPING, info['state'])
        self.assertEqual(ProcessStates.STOPPING, process.state)
        self.assertEqual('', process.extra_args)
        self.assertSetEqual({'10.0.0.2'}, process.running_nodes)
        self.assertEqual(4321, info['pid'])
        self.assertEqual(35, info['now'])
        self.assertEqual(20, info['start'])
        self.assertEqual(15, info['uptime'])
        self.assertTrue(info['expected'])
        # 8. update with an STOPPED event
        process.update_info('10.0.0.2', {'state': ProcessStates.STOPPED,
                                         'now': 40,
                                         'extra_args': ''})
        # test last event info stored
        self.assertGreaterEqual(process.last_event_time, last_event_time)
        last_event_time = process.last_event_time
        self.assertEqual(info['local_time'], last_event_time)
        # check changes
        self.assertEqual(ProcessStates.STOPPED, info['state'])
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertEqual('', process.extra_args)
        self.assertFalse(process.running_nodes)
        self.assertEqual(4321, info['pid'])
        self.assertEqual(40, info['now'])
        self.assertEqual(20, info['start'])
        self.assertEqual(0, info['uptime'])
        self.assertTrue(info['expected'])

    def test_update_times(self):
        """ Test the update of the time entries for a process info belonging to a ProcessStatus. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # add 2 process infos into a process status
        info = any_process_info_by_state(ProcessStates.STOPPING)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.STOPPED))
        # get their time values
        now_1 = process.info_map['10.0.0.1']['now']
        uptime_1 = process.info_map['10.0.0.1']['uptime']
        now_2 = process.info_map['10.0.0.2']['now']
        # update times on address 2
        process.update_times('10.0.0.2', now_2 + 10)
        # check that nothing changed for address 1
        self.assertEqual(now_1, process.info_map['10.0.0.1']['now'])
        self.assertEqual(uptime_1, process.info_map['10.0.0.1']['uptime'])
        # check that times changed for address 2 (uptime excepted)
        self.assertEqual(now_2 + 10, process.info_map['10.0.0.2']['now'])
        self.assertEqual(0, process.info_map['10.0.0.2']['uptime'])
        # update times on address 1
        process.update_times('10.0.0.1', now_1 + 20)
        # check that times changed for address 1 (including uptime)
        self.assertEqual(now_1 + 20, process.info_map['10.0.0.1']['now'])
        self.assertEqual(uptime_1 + 20, process.info_map['10.0.0.1']['uptime'])
        # check that nothing changed for address 2
        self.assertEqual(now_2 + 10, process.info_map['10.0.0.2']['now'])
        self.assertEqual(0, process.info_map['10.0.0.2']['uptime'])

    def test_update_uptime(self):
        """ Test the update of uptime entry in a Process info dictionary. """
        from supvisors.process import ProcessStatus
        # check times on a RUNNING process info
        info = {'start': 50, 'now': 75}
        for state in _process_states_by_code:
            info['state'] = state
            ProcessStatus.update_uptime(info)
            if state in [ProcessStates.RUNNING, ProcessStates.STOPPING]:
                self.assertEqual(25, info['uptime'])
            else:
                self.assertEqual(0, info['uptime'])

    def test_invalidate_nodes(self):
        """ Test the invalidation of nodes. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # create conflict directly with 3 process info
        info = any_process_info_by_state(ProcessStates.BACKOFF)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        process.add_info('10.0.0.2', any_process_info_by_state(ProcessStates.RUNNING))
        process.add_info('10.0.0.3', any_process_info_by_state(ProcessStates.STARTING))
        # check the conflict
        self.assertTrue(process.conflicting())
        self.assertEqual(ProcessStates.RUNNING, process.state)
        # invalidate RUNNING one
        process.invalidate_node('10.0.0.2', False)
        # check state became UNKNOWN on invalidated address
        self.assertEqual(ProcessStates.UNKNOWN, process.info_map['10.0.0.2']['state'])
        # check the conflict
        self.assertTrue(process.conflicting())
        # check new synthetic state
        self.assertEqual(ProcessStates.BACKOFF, process.state)
        # invalidate BACKOFF one
        process.invalidate_node('10.0.0.1', False)
        # check state became UNKNOWN on invalidated address
        self.assertEqual(ProcessStates.UNKNOWN, process.info_map['10.0.0.1']['state'])
        # check 1 address: no conflict
        self.assertFalse(process.conflicting())
        # check synthetic state (running process)
        self.assertEqual(ProcessStates.STARTING, process.state)
        # invalidate STARTING one
        process.invalidate_node('10.0.0.3', True)
        # check state became UNKNOWN on invalidated address
        self.assertEqual(ProcessStates.UNKNOWN, process.info_map['10.0.0.3']['state'])
        # check 0 address: no conflict
        self.assertFalse(process.conflicting())
        # check that synthetic state became FATAL
        self.assertEqual(ProcessStates.FATAL, process.state)
        # check that failure_handler is notified
        self.assertEqual([call(process)], self.supvisors.failure_handler.add_default_job.call_args_list)
        # add one STOPPING
        process.add_info('10.0.0.4', any_process_info_by_state(ProcessStates.STOPPING))
        # check state STOPPING
        self.assertEqual(ProcessStates.STOPPING, process.state)
        # invalidate STOPPING one
        process.invalidate_node('10.0.0.4', False)
        # check state became UNKNOWN on invalidated address
        self.assertEqual(ProcessStates.UNKNOWN, process.info_map['10.0.0.4']['state'])
        # check that synthetic state became STOPPED
        self.assertEqual(ProcessStates.STOPPED, process.state)

    def test_update_status(self):
        """ Test the update of state and running addresses. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # update_status is called in the construction
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertFalse(process.running_nodes)
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertTrue(process.expected_exit)
        # replace with an EXITED process info
        process.info_map['10.0.0.1'] = any_process_info_by_state(ProcessStates.EXITED)
        process.update_status('10.0.0.1', ProcessStates.EXITED, False)
        self.assertFalse(process.running_nodes)
        self.assertEqual(ProcessStates.EXITED, process.state)
        self.assertFalse(process.expected_exit)
        # add a STARTING process info
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
        process.update_status('10.0.0.2', ProcessStates.STARTING, True)
        self.assertSetEqual({'10.0.0.2'}, process.running_nodes)
        self.assertEqual(ProcessStates.STARTING, process.state)
        self.assertTrue(process.expected_exit)
        # add a BACKOFF process info
        process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.BACKOFF)
        process.update_status('10.0.0.3', ProcessStates.STARTING, True)
        self.assertSetEqual({'10.0.0.3', '10.0.0.2'}, process.running_nodes)
        self.assertEqual(ProcessStates.BACKOFF, process.state)
        self.assertTrue(process.expected_exit)
        # replace STARTING process info with RUNNING
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
        process.update_status('10.0.0.2', ProcessStates.RUNNING, True)
        self.assertSetEqual({'10.0.0.3', '10.0.0.2'}, process.running_nodes)
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertTrue(process.expected_exit)
        # replace BACKOFF process info with FATAL
        process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.FATAL)
        process.update_status('10.0.0.3', ProcessStates.FATAL, False)
        self.assertSetEqual({'10.0.0.2'}, process.running_nodes)
        self.assertEqual(ProcessStates.RUNNING, process.state)
        self.assertTrue(process.expected_exit)
        # replace RUNNING process info with STOPPED
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STOPPED)
        process.update_status('10.0.0.2', ProcessStates.STOPPED, False)
        self.assertFalse(process.running_nodes)
        self.assertEqual(ProcessStates.STOPPED, process.state)
        self.assertFalse(process.expected_exit)

    def test_evaluate_conflict(self):
        """ Test the determination of a synthetic state in case of conflict. """
        from supervisor.states import ProcessStates
        from supvisors.process import ProcessStatus
        # when there is only one STOPPED process info, there is no conflict
        info = any_process_info_by_state(ProcessStates.STOPPED)
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        process.add_info('10.0.0.1', info)
        self.assertFalse(process.evaluate_conflict())
        self.assertEqual(ProcessStates.STOPPED, process.state)
        # the addition of one RUNNING process info does not raise any conflict
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.RUNNING)
        process.running_nodes = {'10.0.0.2'}
        self.assertFalse(process.evaluate_conflict())
        # the addition of one STARTING process raises a conflict
        process.info_map['10.0.0.3'] = any_process_info_by_state(ProcessStates.STARTING)
        process.running_nodes.add('10.0.0.3')
        self.assertTrue(process.evaluate_conflict())
        self.assertEqual(ProcessStates.RUNNING, process.state)
        # replace the RUNNING process info with a BACKOFF process info
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.BACKOFF)
        self.assertTrue(process.evaluate_conflict())
        self.assertEqual(ProcessStates.BACKOFF, process.state)
        # replace the BACKOFF process info with a STARTING process info
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.STARTING)
        self.assertTrue(process.evaluate_conflict())
        self.assertEqual(ProcessStates.STARTING, process.state)
        # replace the STARTING process info with an EXITED process info
        process.info_map['10.0.0.2'] = any_process_info_by_state(ProcessStates.EXITED)
        process.running_nodes.remove('10.0.0.2')
        self.assertFalse(process.evaluate_conflict())
        self.assertEqual(ProcessStates.STARTING, process.state)

    def test_running_state(self):
        """ Test the choice of a single state among a list of states. """
        from supervisor.states import ProcessStates, STOPPED_STATES, RUNNING_STATES
        from supvisors.process import ProcessStatus
        # check running states with several combinations
        self.assertEqual(ProcessStates.UNKNOWN,
                         ProcessStatus.running_state(STOPPED_STATES))
        self.assertEqual(ProcessStates.UNKNOWN,
                         ProcessStatus.running_state([ProcessStates.STOPPING]))
        self.assertEqual(ProcessStates.RUNNING,
                         ProcessStatus.running_state(RUNNING_STATES))
        self.assertEqual(ProcessStates.BACKOFF,
                         ProcessStatus.running_state([ProcessStates.STARTING, ProcessStates.BACKOFF]))
        self.assertEqual(ProcessStates.STARTING,
                         ProcessStatus.running_state([ProcessStates.STARTING]))
        self.assertEqual(ProcessStates.RUNNING,
                         ProcessStatus.running_state([ProcessStates.STOPPING, *RUNNING_STATES, *STOPPED_STATES]))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
