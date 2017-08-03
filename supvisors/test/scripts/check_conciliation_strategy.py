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

from Queue import Empty

from supervisor.states import ProcessStates
from supervisor.xmlrpc import Faults

from supvisors.ttypes import ConciliationStrategies, SupvisorsStates

from scripts.event_queues import SupvisorsEventQueues
from scripts.running_addresses import RunningAddressesTest


class ConciliationStrategyTest(RunningAddressesTest):
    """ Test case to check the conciliation of Supvisors.
    The aim is to test user and auto conciliation, depending on the
    configuration.
    """

    def setUp(self):
        """ Get initial status:
        - one movie_server running on each address. """
        RunningAddressesTest.setUp(self)
        # store initial process status
        process_info = self.local_supvisors.get_process_info('database:*')
        self.running_processes = {info['process_name']: info['addresses']
            for info in process_info
                if info['statecode'] == ProcessStates.RUNNING}
        self.assertItemsEqual(self.running_processes.keys(),
            ['movie_server_01', 'movie_server_02', 'movie_server_03'])
        # check that there is no conflict before to start testing
        self._check_no_conflict()

    def test_conciliation(self):
        """ Check depending on the configuration. """
        # test depends on configuration
        strategies = self.local_proxy.supvisors.get_strategies()
        strategy = ConciliationStrategies._from_string(strategies['conciliation'])
        if strategy == ConciliationStrategies.USER:
            print('### Testing USER conciliation')
            self._check_conciliation_user()
        else:
            print('### Testing Automatic conciliation with {}'.format(
                strategies['conciliation']))
            self._check_conciliation_auto()

    def _get_next_supvisors_event(self):
        """ Return next Supvisors event from queue. """
        try:
            return self.evloop.supvisors_queue.get(True, 15)
        except Empty:
            self.fail('failed to get the expected Supvisors status')

    def _check_conciliation_auto(self):
        """ Test the conciliation after creating conflicts. """
        # create the conflicts
        self._create_database_conflicts()
        # check process events
        # cannot check using RPC as conciliation will be triggered automatically
        # so check only the Supvisors state transitions
        data = self._get_next_supvisors_event()
        self.assertEqual(SupvisorsStates.CONCILIATION,
                         data['statecode'])
        data = self._get_next_supvisors_event()
        self.assertEqual(SupvisorsStates.OPERATION,
                         data['statecode'])
        # check that there is no conflict anymore
        self._check_no_conflict()

    def _check_conciliation_user(self):
        """ Test the conciliation after creating conflicts. """
        # create the conflicts and check the CONCILIATION status
        self._create_database_conflicts()
        # check supvisors event: CONCILIATION state is expected
        data = self._get_next_supvisors_event()
        self.assertEqual(SupvisorsStates.CONCILIATION,
                         data['statecode'])
        # check the conflicts and the CONCILIATION status using RPC
        self._check_database_conflicts()
        # conciliate the conflicts with RPC requests
        # come back to initial state
        for process, addresses in self.running_processes.items():
            for address in self.running_addresses:
                if address not in addresses:
                    proxy = self.proxies[address].supervisor
                    proxy.stopProcess('database:' + process)
        # check supvisors event: OPERATION state is expected
        data = self._get_next_supvisors_event()
        self.assertEqual(SupvisorsStates.OPERATION,
                         data['statecode'])
        # check that there is no conflict anymore
        self._check_no_conflict()

    def _check_no_conflict(self):
        """ Check that there is no conflict. """
        for proxy in self.proxies.values():
            # test that Supvisors is in OPERATION state
            supvisors_state = proxy.supvisors.get_supvisors_state()
            self.assertEqual(SupvisorsStates.OPERATION,
                             supvisors_state['statecode'])
            # test that Supvisors conflicts is empty
            self.assertEqual([], proxy.supvisors.get_conflicts())

    def _create_database_conflicts(self):
        """ Create conflicts on database application. """
        # start all movie_server programs on all addresses
        for proxy in self.proxies.values():
            for idx in range(1, 4):
                try:
                    proxy.supervisor.startProcess('database:movie_server_0%d' % idx)
                except xmlrpclib.Fault, exc:
                    self.assertEqual(Faults.ALREADY_STARTED, exc.faultCode)

    def _check_database_conflicts(self):
        """ Test conflicts on database application using RPC. """
        # check that the conflicts are detected in all Supvisors instances
        for proxy in self.proxies.values():
            # test that Supvisors is in CONCILIATION state (in all instances)
            supvisors_state = proxy.supvisors.get_supvisors_state()
            self.assertEqual(SupvisorsStates.CONCILIATION,
                             supvisors_state['statecode'])
            # test Supvisors conflicts
            conflicts = proxy.supvisors.get_conflicts()
            process_names = [proc['process_name'] for proc in conflicts]
            self.assertItemsEqual(process_names,
                ['movie_server_01', 'movie_server_02', 'movie_server_03'])


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(
        description='Check the Supvisors conciliation strategies.')
    parser.add_argument('-p', '--port', type=int, default=60002,
                        help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
