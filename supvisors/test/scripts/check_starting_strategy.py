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
import unittest

from supervisor.compat import xmlrpclib
from supervisor.states import STOPPED_STATES
from supervisor.xmlrpc import Faults

from supvisors.ttypes import SupvisorsInstanceStates, StartingStrategies

from .event_queues import SupvisorsEventQueues
from .running_identifiers import RunningIdentifiersTest


class StartingStrategyTest(RunningIdentifiersTest):
    """ Test case to check the loading strategies of Supvisors. """

    def setUp(self):
        """ Get initial status. """
        RunningIdentifiersTest.setUp(self)
        # check the loading on running instances
        # initial state is cliche81=14% cliche82=15% cliche83=5%
        self._refresh_loading()
        assert list(self.loading.values()) == [10, 15, 9]
        # check that 10 converter programs are STOPPED
        processes_info = self.local_supvisors.get_process_info('my_movies:*')
        converters = [info for info in processes_info
                      if info['process_name'].startswith('converter') and info['statecode'] in STOPPED_STATES]
        self.assertEqual(10, len(converters))
        # check that 10 converter programs are configured with loading 25
        processes_rules = self.local_supvisors.get_process_rules('my_movies:*')
        converters = [rules for rules in processes_rules
                      if rules['process_name'].startswith('converter') and rules['expected_loading'] == 25]
        self.assertEqual(10, len(converters))

    def tearDown(self):
        """ The tearDown stops the converters that may have been started. """
        # stop all converters
        for idx in range(10):
            try:
                program = 'my_movies:converter_0%d' % idx
                self.local_supvisors.stop_process(program)
            except Exception:
                pass
        # call parent
        RunningIdentifiersTest.tearDown(self)

    def _refresh_loading(self):
        """ Get the current loading status. """
        nodes_info = self.local_supvisors.get_all_instances_info()
        self.loading = {info['identifier']: info['loading']
                        for info in nodes_info
                        if info['statecode'] == SupvisorsInstanceStates.RUNNING.value}

    def _start_converter(self, idx):
        """ Get the current loading status. """
        self.local_supvisors.start_process(self.strategy.value, 'my_movies:converter_0%d' % idx)
        # wait for event STARTING
        event = self._get_next_process_event()
        assert {'group': 'my_movies', 'name': 'converter_0%d' % idx, 'state': 10}.items() < event.items()
        # wait for event RUNNING
        event = self._get_next_process_event()
        assert {'group': 'my_movies', 'name': 'converter_0%d' % idx, 'state': 20}.items() < event.items()
        # refresh the node loadings
        self._refresh_loading()

    def _start_converter_failed(self, idx):
        """ Get the current loading status. """
        with self.assertRaises(xmlrpclib.Fault) as exc:
            self.local_supvisors.start_process(self.strategy.value, 'my_movies:converter_0%d' % idx)
        self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.faultCode)
        self.assertEqual('ABNORMAL_TERMINATION: my_movies:converter_0%d' % idx, exc.exception.faultString)
        # wait for event FATAL
        event = self._get_next_process_event()
        assert {'group': 'my_movies', 'name': 'converter_0%d' % idx, 'state': 200}.items() < event.items()
        # refresh the node loadings
        self._refresh_loading()

    def test_config(self):
        """ Test the CONFIG starting strategy.
        Start converters and check they have been started on the first node
        available defined in the program section of the rules file. """
        print('### Testing CONFIG starting strategy')
        self.strategy = StartingStrategies.CONFIG
        # no node config for almost all converters (excepted 04 and 07)
        # so applicable order is the one defined in the supvisors section,
        # i.e. cliche81, cliche82, cliche83, cliche84 (not running)
        self._start_converter(0)
        self.assertEqual([35, 15, 9], list(self.loading.values()))
        # continue with cliche81
        self._start_converter(1)
        self.assertEqual([60, 15, 9], list(self.loading.values()))
        # try with converter_04 to check the alt config where cliche83 comes first
        self._start_converter(4)
        self.assertEqual([60, 15, 34], list(self.loading.values()))
        # there is still place on cliche81
        self._start_converter(2)
        self.assertEqual([85, 15, 34], list(self.loading.values()))
        # cliche81 is full. cliche82 will be used now
        self._start_converter(3)
        self.assertEqual([85, 40, 34], list(self.loading.values()))
        # there is still place on cliche82
        # try with converter_07 to check the alt config
        # cliche81 is full, so second node in config will be used (cliche83)
        self._start_converter(7)
        self.assertEqual([85, 40, 59], list(self.loading.values()))
        # there is still place on cliche82
        self._start_converter(5)
        self.assertEqual([85, 65, 59], list(self.loading.values()))
        # cliche81 is full. cliche82 will be used now
        self._start_converter(6)
        self.assertEqual([85, 90, 59], list(self.loading.values()))
        # cliche81 & cliche82 are full. cliche83 will be used now
        self._start_converter(8)
        self.assertEqual([85, 90, 84], list(self.loading.values()))
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.assertEqual([85, 90, 84], list(self.loading.values()))

    def test_less_loaded(self):
        """ Test the LESS_LOADED starting strategy.
        Start converters and check they have been started on the node having the lowest loading. """
        print('### Testing LESS_LOADED starting strategy')
        self.strategy = StartingStrategies.LESS_LOADED
        self._start_converter(0)
        self.assertEqual([10, 15, 34], list(self.loading.values()))
        self._start_converter(1)
        self.assertEqual([35, 15, 34], list(self.loading.values()))
        self._start_converter(2)
        self.assertEqual([35, 40, 34], list(self.loading.values()))
        self._start_converter(3)
        self.assertEqual([35, 40, 59], list(self.loading.values()))
        self._start_converter(4)
        self.assertEqual([60, 40, 59], list(self.loading.values()))
        self._start_converter(5)
        self.assertEqual([60, 65, 59], list(self.loading.values()))
        self._start_converter(6)
        self.assertEqual([60, 65, 84], list(self.loading.values()))
        self._start_converter(7)
        self.assertEqual([85, 65, 84], list(self.loading.values()))
        self._start_converter(8)
        self.assertEqual([85, 90, 84], list(self.loading.values()))
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.assertEqual([85, 90, 84], list(self.loading.values()))

    def test_most_loaded(self):
        """ Test the MOST_LOADED starting strategy.
        Start converters and check they have been started on the node having the highest loading. """
        print('### Testing MOST_LOADED starting strategy')
        self.strategy = StartingStrategies.MOST_LOADED
        self._start_converter(0)
        self.assertEqual([10, 40, 9], list(self.loading.values()))
        self._start_converter(1)
        self.assertEqual([10, 65, 9], list(self.loading.values()))
        self._start_converter(2)
        self.assertEqual([10, 90, 9], list(self.loading.values()))
        self._start_converter(3)
        self.assertEqual([35, 90, 9], list(self.loading.values()))
        self._start_converter(4)
        self.assertEqual([60, 90, 9], list(self.loading.values()))
        self._start_converter(5)
        self.assertEqual([85, 90, 9], list(self.loading.values()))
        self._start_converter(6)
        self.assertEqual([85, 90, 34], list(self.loading.values()))
        self._start_converter(7)
        self.assertEqual([85, 90, 59], list(self.loading.values()))
        self._start_converter(8)
        self.assertEqual([85, 90, 84], list(self.loading.values()))
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.assertEqual([85, 90, 84], list(self.loading.values()))

    def test_local(self):
        """ Test the LOCAL starting strategy.
        Start converters and check they have been started on the node having the highest loading. """
        print('### Testing LOCAL starting strategy')
        self.strategy = StartingStrategies.LOCAL
        # this test should be started only from cliche81 so processes should be started only on cliche81
        self._start_converter(0)
        self.assertEqual([35, 15, 9], list(self.loading.values()))
        self._start_converter(1)
        self.assertEqual([60, 15, 9], list(self.loading.values()))
        self._start_converter(2)
        self.assertEqual([85, 15, 9], list(self.loading.values()))
        # next converter cannot be started: no resource left
        self._start_converter_failed(3)
        self.assertEqual([85, 15, 9], list(self.loading.values()))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Check the Supvisors starting strategies.')
    parser.add_argument('-p', '--port', type=int, default=60002, help='the event port of Supvisors')
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
