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
        self._refresh_loading()
        # check that 15 converter programs are STOPPED
        processes_info = self.local_supvisors.get_process_info('my_movies:*')
        converters = [info for info in processes_info
                      if info['process_name'].startswith('converter') and info['statecode'] in STOPPED_STATES]
        self.assertEqual(15, len(converters))
        # check that 15 converter programs are configured with loading 20
        processes_rules = self.local_supvisors.get_process_rules('my_movies:*')
        converters = [rules for rules in processes_rules
                      if rules['process_name'].startswith('converter') and rules['expected_loading'] == 20]
        self.assertEqual(15, len(converters))

    def tearDown(self):
        """ The tearDown stops the converters that may have been started. """
        # stop all converters
        for idx in range(15):
            try:
                self.local_supvisors.stop_process(f'my_movies:converter_{idx:02d}')
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
        self.local_supvisors.start_process(self.strategy.value, f'my_movies:converter_{idx:02d}')
        # wait for event STARTING
        event = self._get_next_process_event()
        assert {'group': 'my_movies', 'name': f'converter_{idx:02d}', 'state': 10}.items() < event.items()
        # wait for event RUNNING
        event = self._get_next_process_event()
        assert {'group': 'my_movies', 'name': f'converter_{idx:02d}', 'state': 20}.items() < event.items()
        # refresh the node loadings
        self._refresh_loading()

    def _start_converter_failed(self, idx):
        """ Get the current loading status. """
        with self.assertRaises(xmlrpclib.Fault) as exc:
            self.local_supvisors.start_process(self.strategy.value, f'my_movies:converter_{idx:02d}')
        self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.faultCode)
        self.assertEqual(f'ABNORMAL_TERMINATION: failed to start my_movies:converter_{idx:02d}',
                         exc.exception.faultString)
        # wait for event FATAL
        event = self._get_next_process_event()
        assert {'group': 'my_movies', 'name': f'converter_{idx:02d}', 'state': 200}.items() < event.items()
        # refresh the node loadings
        self._refresh_loading()

    def check_loading(self, loadings):
        """ Check the nodes loading. """
        # print(loadings)
        self.assertEqual(self.loading, {'17.0.1.11:60000': loadings[0],
                                        'supv02:60000': loadings[1],
                                        '17.0.1.11:30000': loadings[2]})

    def test_config(self):
        """ Test the CONFIG starting strategy.
        Start converters and check they have been started on the first node available defined in the program section
        of the rules file. """
        print('### Testing CONFIG starting strategy')
        # initial state is supv-01=10% rocky52=15% supv-03=9%
        # supv-01 and supv-03 are on the same host rocky51
        self.check_loading([10, 15, 9])
        self.strategy = StartingStrategies.CONFIG
        # no node config for almost all converters (excepted 04 and 07)
        # so applicable order is the one defined in the supvisors section,
        # i.e. supv-01, rocky52, supv-03, rocky54 (not running)
        self._start_converter(0)
        self.check_loading([30, 15, 9])
        # continue with supv-01
        self._start_converter(1)
        self.check_loading([50, 15, 9])
        # try with converter_04 to check the alt config where supv-03 comes first
        self._start_converter(4)
        self.check_loading([50, 15, 29])
        # converter 7 can only be started on rocky52
        self._start_converter(7)
        self.check_loading([50, 35, 29])
        # there is still place on rocky51 / supv-01
        self._start_converter(2)
        self.check_loading([70, 35, 29])
        # rocky51 is full. rocky52 will be used now
        self._start_converter(3)
        self.check_loading([70, 55, 29])
        # there is still place on rocky52
        self._start_converter(5)
        self.check_loading([70, 75, 29])
        # there is still place on rocky52
        self._start_converter(6)
        self.check_loading([70, 95, 29])
        # rocky51 & rocky52 are full
        self._start_converter_failed(8)
        self.check_loading([70, 95, 29])

    def test_less_loaded(self):
        """ Test the LESS_LOADED starting strategy.
        Start converters and check they have been started on the Supvisors instance having the lowest load. """
        print('### Testing LESS_LOADED starting strategy')
        # initial state is supv-01=10% rocky52=15% supv-03=9%
        self.check_loading([10, 15, 9])
        self.strategy = StartingStrategies.LESS_LOADED
        self._start_converter(0)
        self.check_loading([10, 15, 29])
        self._start_converter(1)
        self.check_loading([30, 15, 29])
        self._start_converter(2)
        self.check_loading([30, 35, 29])
        self._start_converter(3)
        self.check_loading([30, 35, 49])
        self._start_converter(5)
        self.check_loading([50, 35, 49])
        # converter 4 cannot be started on rocky52 but rocky51 (including supv-01 and supv-03) is full
        self._start_converter_failed(4)
        self.check_loading([50, 35, 49])
        self._start_converter(6)
        self.check_loading([50, 55, 49])
        # converter 7 can only be started on rocky52
        self._start_converter(7)
        self.check_loading([50, 75, 49])
        self._start_converter(8)
        self.check_loading([50, 95, 49])
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.check_loading([50, 95, 49])

    def test_less_loaded_node(self):
        """ Test the LESS_LOADED_NODE starting strategy.
        Start converters and check they have been started on the node having the lowest load. """
        print('### Testing LESS_LOADED_NODE starting strategy')
        # initial state is supv-01=10% rocky52=15% supv-03=9%
        self.check_loading([10, 15, 9])
        self.strategy = StartingStrategies.LESS_LOADED_NODE
        self._start_converter(0)
        self.check_loading([10, 35, 9])
        self._start_converter(1)
        self.check_loading([10, 35, 29])
        self._start_converter(2)
        self.check_loading([10, 55, 29])
        self._start_converter(3)
        self.check_loading([30, 55, 29])
        # converter 4 cannot be started on rocky52
        self._start_converter(4)
        self.check_loading([30, 55, 49])
        self._start_converter(5)
        self.check_loading([30, 75, 49])
        self._start_converter(6)
        self.check_loading([30, 95, 49])
        # converter 7 can only be started on rocky52
        self._start_converter_failed(7)
        self.check_loading([30, 95, 49])
        self._start_converter(8)
        self.check_loading([50, 95, 49])
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.check_loading([50, 95, 49])

    def test_most_loaded(self):
        """ Test the MOST_LOADED starting strategy.
        Start converters and check they have been started on the Supvisors instance having the highest loading. """
        print('### Testing MOST_LOADED starting strategy')
        # initial state is supv-01=10% rocky52=15% supv-03=9%
        self.check_loading([10, 15, 9])
        self.strategy = StartingStrategies.MOST_LOADED
        self._start_converter(0)
        self.check_loading([10, 35, 9])
        self._start_converter(1)
        self.check_loading([10, 55, 9])
        self._start_converter(2)
        self.check_loading([10, 75, 9])
        self._start_converter(3)
        self.check_loading([10, 95, 9])
        # converter 4 cannot be started on rocky52
        self._start_converter(4)
        self.check_loading([30, 95, 9])
        self._start_converter(5)
        self.check_loading([50, 95, 9])
        self._start_converter(6)
        self.check_loading([70, 95, 9])
        # converter 7 can only be started on rocky52
        self._start_converter_failed(7)
        self.check_loading([70, 95, 9])
        self._start_converter(8)
        self.check_loading([90, 95, 9])
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.check_loading([90, 95, 9])

    def test_most_loaded_node(self):
        """ Test the MOST_LOADED_NODE starting strategy.
        Start converters and check they have been started on the node having the highest loading. """
        print('### Testing MOST_LOADED_NODE starting strategy')
        # initial state is supv-01=10% rocky52=15% supv-03=9%
        self.check_loading([10, 15, 9])
        self.strategy = StartingStrategies.MOST_LOADED_NODE
        self._start_converter(0)
        self.check_loading([30, 15, 9])
        self._start_converter(1)
        self.check_loading([50, 15, 9])
        self._start_converter(2)
        self.check_loading([70, 15, 9])
        self._start_converter(3)
        self.check_loading([90, 15, 9])
        # converter 4 cannot be started on rocky52
        self._start_converter_failed(4)
        self.check_loading([90, 15, 9])
        self._start_converter(5)
        self.check_loading([90, 35, 9])
        self._start_converter(6)
        self.check_loading([90, 55, 9])
        # converter 7 can only be started on rocky52
        self._start_converter(7)
        self.check_loading([90, 75, 9])
        self._start_converter(8)
        self.check_loading([90, 95, 9])
        # last converter cannot be started: no resource left
        self._start_converter_failed(9)
        self.check_loading([90, 95, 9])

    def test_local(self):
        """ Test the LOCAL starting strategy.
        Start converters and check they have been started on the node having the highest loading. """
        print('### Testing LOCAL starting strategy')
        # initial state is supv-01=10% rocky52=15% supv-03=9%
        self.check_loading([10, 15, 9])
        self.strategy = StartingStrategies.LOCAL
        # this test should be started only from supv-01 so processes should be started only on supv-01
        self._start_converter(0)
        self.check_loading([30, 15, 9])
        self._start_converter(1)
        self.check_loading([50, 15, 9])
        self._start_converter(2)
        self.check_loading([70, 15, 9])
        self._start_converter(3)
        self.check_loading([90, 15, 9])
        # next converter cannot be started: no resource left
        self._start_converter_failed(4)
        self.check_loading([90, 15, 9])


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
