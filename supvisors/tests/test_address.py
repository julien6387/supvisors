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
import time
import unittest

from supvisors.tests.base import (MockedSupvisors,
                                  any_process_info,
                                  database_copy,
                                  CompatTestCase)


class AddressTest(CompatTestCase):
    """ Test case for the address module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()
        from supvisors.ttypes import AddressStates
        self.all_states = AddressStates.values()

    def test_create(self):
        """ Test the values set at construction. """
        from supvisors.address import AddressStatus
        from supvisors.ttypes import AddressStates
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        # test all AddressStatus values
        self.assertIs(self.supvisors.logger, status.logger)
        self.assertEqual('10.0.0.1', status.address_name)
        self.assertEqual(AddressStates.UNKNOWN, status.state)
        self.assertEqual(0, status.remote_time)
        self.assertEqual(0, status.local_time)
        self.assertDictEqual({}, status.processes)

    def test_isolation(self):
        """ Test the in_isolation method. """
        from supvisors.address import AddressStatus
        from supvisors.ttypes import AddressStates
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        for state in self.all_states:
            status._state = state
            self.assertTrue(status.in_isolation() and state in [AddressStates.ISOLATING, AddressStates.ISOLATED] or
                            not status.in_isolation() and state not in [AddressStates.ISOLATING,
                                                                        AddressStates.ISOLATED])

    def test_serialization(self):
        """ Test the serial method used to get a serializable form of AddressStatus. """
        import pickle
        from supvisors.address import AddressStatus
        from supvisors.ttypes import AddressStates
        # create address status instance
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        status._state = AddressStates.RUNNING
        status.checked = True
        status.remote_time = 50
        status.local_time = 60
        # test to_json method
        serialized = status.serial()
        self.assertDictEqual(serialized, {'address_name': '10.0.0.1', 'loading': 0,
                                          'statecode': 2, 'statename': 'RUNNING', 'remote_time': 50, 'local_time': 60})
        # test that returned structure is serializable using pickle
        dumped = pickle.dumps(serialized)
        loaded = pickle.loads(dumped)
        self.assertDictEqual(serialized, loaded)

    def test_transitions(self):
        """ Test the state transitions of AddressStatus. """
        from supvisors.address import AddressStatus
        from supvisors.ttypes import AddressStates, InvalidTransition
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        for state1 in self.all_states:
            for state2 in self.all_states:
                # check all possible transitions from each state
                status._state = state1
                if state2 in status._Transitions[state1]:
                    status.state = state2
                    self.assertEqual(state2, status.state)
                    self.assertEqual(AddressStates.to_string(state2), status.state_string())
                elif state1 == state2:
                    self.assertEqual(state1, status.state)
                else:
                    with self.assertRaises(InvalidTransition):
                        status.state = state2

    def test_add_process(self):
        """ Test the add_process method. """
        from supvisors.address import AddressStatus
        from supvisors.process import ProcessStatus
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        info = any_process_info()
        process = ProcessStatus(info['group'], info['name'], self.supvisors)
        status.add_process(process)
        # check that process is stored
        self.assertIn(process.namespec(), status.processes.keys())
        self.assertIs(process, status.processes[process.namespec()])

    def test_times(self):
        """ Test the update_times method. """
        from supervisor.states import ProcessStates
        from supvisors.address import AddressStatus
        from supvisors.process import ProcessStatus
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        # add processes
        for info in database_copy():
            process = ProcessStatus(info['group'], info['name'], self.supvisors)
            process.add_info('10.0.0.1', info)
            status.add_process(process)
        # get current process times
        ref_data = {process.namespec(): (process.state, info['now'], info['uptime'])
                    for process in status.processes.values()
                    for info in [process.infos['10.0.0.1']]}
        # update times and check
        now = int(time.time())
        status.update_times(now + 10, now)
        self.assertEqual(now + 10, status.remote_time)
        self.assertEqual(now, status.local_time)
        # test process times: only RUNNING and STOPPING have a positive uptime
        new_data = {process.namespec(): (process.state, info['now'], info['uptime'])
                    for process in status.processes.values()
                    for info in [process.infos['10.0.0.1']]}
        for namespec, new_info in new_data.items():
            ref_info = ref_data[namespec]
            self.assertEqual(new_info[0], ref_info[0])
            self.assertGreater(new_info[1], ref_info[1])
            if new_info[0] in [ProcessStates.RUNNING, ProcessStates.STOPPING]:
                self.assertGreater(new_info[2], ref_info[2])
            else:
                self.assertEqual(new_info[2], ref_info[2])

    def test_running_process(self):
        """ Test the running_process method. """
        from supvisors.address import AddressStatus
        from supvisors.process import ProcessStatus
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        for info in database_copy():
            process = ProcessStatus(info['group'], info['name'], self.supvisors)
            process.add_info('10.0.0.1', info)
            status.add_process(process)
        # check the name of the running processes
        self.assertItemsEqual(['late_segv', 'segv', 'xfontsel', 'yeux_01'],
                              [proc.process_name for proc in status.running_processes()])

    def test_pid_process(self):
        """ Test the pid_process method. """
        from supvisors.address import AddressStatus
        from supvisors.process import ProcessStatus
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        for info in database_copy():
            process = ProcessStatus(info['group'], info['name'], self.supvisors)
            process.add_info('10.0.0.1', info)
            status.add_process(process)
        # check the namespec and pid of the running processes
        self.assertItemsEqual([('sample_test_1:xfontsel', 80879), ('sample_test_2:yeux_01', 80882)],
                              status.pid_processes())

    def test_loading(self):
        """ Test the loading method. """
        from supvisors.address import AddressStatus
        from supvisors.process import ProcessStatus
        status = AddressStatus('10.0.0.1', self.supvisors.logger)
        for info in database_copy():
            process = ProcessStatus(info['group'], info['name'], self.supvisors)
            process.add_info('10.0.0.1', info)
            status.add_process(process)
        # check the loading of the address: gives 5 (1 per running process) by default because no rule has been loaded
        self.assertEqual(4, status.loading())
        # change expected_loading of any stopped process
        process = random.choice([proc for proc in status.processes.values() if proc.stopped()])
        process.rules.expected_loading = 50
        self.assertEqual(4, status.loading())
        # change expected_loading of any running process
        process = random.choice([proc for proc in status.processes.values() if proc.running()])
        process.rules.expected_loading = 50
        self.assertEqual(53, status.loading())


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
