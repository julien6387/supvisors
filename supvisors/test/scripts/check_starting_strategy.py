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
import unittest
import xmlrpclib

from supervisor.states import STOPPED_STATES
from supervisor.xmlrpc import Faults

from supvisors.ttypes import AddressStates, StartingStrategies

from scripts.event_queues import SupvisorsEventQueues
from scripts.running_addresses import RunningAddressesTest


class StartingStrategyTest(RunningAddressesTest):
    """ Test case to check the loading strategies of Supvisors. """

    def setUp(self):
        """ Get initial status. """
        RunningAddressesTest.setUp(self)
        # check the loading on running addresses
        self._refresh_loading()
        self.assertItemsEqual([15, 15, 5], self.loading.values())
        # check that 10 converter programs are STOPPED
        processes_info = self.local_supvisors.get_process_info('my_movies:*')
        converters = [info for info in processes_info
                      if info['process_name'].startswith('converter') and
                      info['statecode'] in STOPPED_STATES]
        self.assertEqual(10, len(converters))
        # check that 10 converter programs are configured with loading 25
        processes_rules = self.local_supvisors.get_process_rules('my_movies:*')
        converters = [rules for rules in processes_rules
                      if rules['process_name'].startswith('converter') and
                      rules['expected_loading'] == 25]
        self.assertEqual(10, len(converters))

    def tearDown(self):
        """ The tearDown stops the converters that may have been started. """
        # stop all converters
        for idx in range(10):
            try:
                program = 'my_movies:converter_0%d' % idx
                self.local_supvisors.stop_process(program)
            except:
                pass
        # call parent
        RunningAddressesTest.tearDown(self)

    def _get_next_process_event(self):
        """ Return next Process event from queue. """
        try:
            return self.evloop.event_queue.get(True, 10)
        except Empty:
            self.fail('failed to get the expected Process event')

    def _refresh_loading(self):
        """ Get the current loading status. """
        addresses_info = self.local_supvisors.get_all_addresses_info()
        self.loading = {info['address_name']: info['loading']
            for info in addresses_info
                if info['statecode'] == AddressStates.RUNNING}
        print self.loading

    def _start_converter(self, idx):
        """ Get the current loading status. """
        self.local_supvisors.start_process(StartingStrategies.LESS_LOADED,
                                           'my_movies:converter_0%d' % idx)
        # wait for events
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'group': 'my_movies',
                                       'name': 'converter_0%d' % idx,
                                       'state': 10}, event)
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'group': 'my_movies',
                                       'name': 'converter_0%d' % idx,
                                       'state': 20}, event)
        # refresh the address loadings
        self._refresh_loading()

    def _test_config(self):
        """ Test the starting strategies iaw the rules defined. """

    def test_less_loaded(self):
        """ Test the LESS_LOADED starting strategy. """
        # start a converter and check it has been started on the address
        # having the lowest loading
        self._start_converter(0)
        self.assertItemsEqual([15, 15, 30], self.loading.values())
        self._start_converter(1)
        self.assertItemsEqual([40, 15, 30], self.loading.values())
        self._start_converter(2)
        self.assertItemsEqual([40, 40, 30], self.loading.values())
        self._start_converter(3)
        self.assertItemsEqual([40, 40, 55], self.loading.values())
        self._start_converter(4)
        self.assertItemsEqual([65, 40, 55], self.loading.values())
        self._start_converter(5)
        self.assertItemsEqual([65, 65, 55], self.loading.values())
        self._start_converter(6)
        self.assertItemsEqual([65, 65, 80], self.loading.values())
        self._start_converter(7)
        self.assertItemsEqual([90, 65, 80], self.loading.values())
        self._start_converter(8)
        self.assertItemsEqual([90, 90, 80], self.loading.values())
        # last converter cannot be started: no resource left
        with self.assertRaises(xmlrpclib.Fault) as exc:
            self._start_converter(9)
        print exc.exception.__dict__
        self.assertEqual(Faults.ABNORMAL_TERMINATION, exc.exception.faultCode)
        self.assertItemsEqual([90, 90, 80], self.loading.values())

    def _test_most_loaded(self):
        """ Test the starting strategies iaw the rules defined. """


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(
        description='Check the Supvisors special functions.')
    parser.add_argument('-p', '--port', type=int, default=60002,
                        help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
