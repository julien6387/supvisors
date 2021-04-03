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
from supervisor.states import ProcessStates
from supervisor.xmlrpc import Faults

from supvisors.ttypes import ConciliationStrategies, StartingStrategies

from scripts.event_queues import SupvisorsEventQueues
from scripts.running_addresses import RunningAddressesTest


class ConciliationStrategyTest(RunningAddressesTest):
    """ Test case to check the conciliation of Supvisors.
    The aim is to test user and auto conciliation, depending on the configuration.
    """

    def setUp(self):
        """ Get initial status (one movie_server running on each address). """
        RunningAddressesTest.setUp(self)
        # store initial process status
        self.running_processes = self._get_movie_servers()
        # expected to be {'movie_server_01': ['cliche01'],
        #                 'movie_server_02': ['cliche03'],
        #                 'movie_server_03': ['cliche02']}
        self.assertItemsEqual(self.running_processes.keys(), ['movie_server_01', 'movie_server_02', 'movie_server_03'])
        running_addresses = set()
        for addresses in self.running_processes.values():
            self.assertEqual(1, len(addresses))
            self.assertNotIn(addresses[0], running_addresses)
            running_addresses.add(addresses[0])
        # check that there is no conflict before to start testing
        self._check_no_conflict()

    def tearDown(self):
        """ Back to initial status (one movie_server running on each address). """
        print('### [INFO] clean-up')
        try:
            self.local_supvisors.restart_application(StartingStrategies.CONFIG.value, 'database')
        except:
            print('### [ERROR] failed to restart database application')
        RunningAddressesTest.tearDown(self)

    def test_conciliation(self):
        """ Check depending on the configuration. """
        # test depends on configuration
        strategies = self.local_proxy.supvisors.get_strategies()
        strategy = ConciliationStrategies[strategies['conciliation']]
        if strategy == ConciliationStrategies.USER:
            print('### [INFO] Testing USER conciliation')
            self._check_conciliation_user_manual()
            self._check_conciliation_user_infanticide()
            self._check_conciliation_user_senicide()
            self._check_conciliation_user_stop()
            self._check_conciliation_user_restart()
            self._check_conciliation_user_running_failure()
        else:
            print('### Testing Automatic conciliation with {}'.format(strategies['conciliation']))
            self._check_conciliation_auto()

    def _check_conciliation_auto(self):
        """ Test the conciliation after creating conflicts. """
        # create the conflicts
        self._create_database_conflicts()
        # cannot check using XML-RPC as conciliation will be triggered
        # automatically so check only the Supvisors state transitions
        event = self._get_next_supvisors_event()
        self.assertEqual('CONCILIATION', event['statename'])
        event = self._get_next_supvisors_event()
        self.assertEqual('OPERATION', event['statename'])
        # check that there is no conflict anymore
        self._check_no_conflict()

    def _check_conciliation_user_manual(self):
        """ Test the USER conciliation with user XML-RPC. """
        print('### [INFO] Testing USER - MANUAL conciliation')

        def conciliation():
            # come back to initial state with XML-RPC
            for process, addresses in self.running_processes.items():
                for address in self.running_addresses:
                    if address not in addresses:
                        self.proxies[address].supervisor.stopProcess('database:' + process)

        self._check_conciliation_user_database(conciliation)

    def _check_conciliation_user_infanticide(self):
        """ Test the INFANTICIDE conciliation on USER request. """
        print('### [INFO] Testing USER - INFANTICIDE conciliation')

        def conciliation():
            self.local_supvisors.conciliate(ConciliationStrategies.INFANTICIDE.value)

        self._check_conciliation_user_database(conciliation)
        # check final status
        ending_status = self._get_movie_servers()
        # expecting initial status
        self.assertDictEqual(self.running_processes, ending_status)

    def _check_conciliation_user_senicide(self):
        """ Test the SENICIDE conciliation on USER request. """
        print('### [INFO] Testing USER - SENICIDE conciliation')

        def conciliation():
            self.local_supvisors.conciliate(ConciliationStrategies.SENICIDE.value)

        self._check_conciliation_user_database(conciliation)
        # check final status
        ending_status = self._get_movie_servers()
        # expected to be {'movie_server_01': ['cliche83'],
        #                 'movie_server_02': ['cliche82'],
        #                 'movie_server_03': ['cliche83']}
        # check that running addresses at the end is not the same as at the
        # beginning for all processes
        for process, addresses in ending_status.items():
            start_address = self.running_processes[process][0]
            self.assertNotEqual(addresses[0], start_address)

    def _check_conciliation_user_stop(self):
        """ Test the STOP conciliation on USER request. """
        print('### [INFO] Testing USER - STOP conciliation')

        def conciliation():
            self.local_supvisors.conciliate(ConciliationStrategies.STOP.value)

        self._check_conciliation_user_database(conciliation)
        # check final status
        ending_status = self._get_movie_servers()
        # expecting all stopped
        self.assertEqual(0, len(ending_status))

    def _check_conciliation_user_restart(self):
        """ Test the RESTART conciliation on USER request. """
        print('### [INFO] Testing USER - RESTART conciliation')

        def conciliation():
            self.local_supvisors.conciliate(ConciliationStrategies.RESTART.value)

        self._check_conciliation_user_database(conciliation)
        # this test is a bit long and produces lots of events
        # so hang on for specific events for test
        # 1. all movie_server programs (9) shall be stopped
        expected_events = [{'name': 'movie_server_0%d' % (idx + 1), 'state': 0, 'address': address}
                           for address in self.running_addresses
                           for idx in range(3)]
        received_events = self.evloop.wait_until_events(self.evloop.event_queue, expected_events, 10)
        self.assertEqual(9, len(received_events))
        self.assertEqual([], expected_events)
        # 2. all movie_server programs shall be running after restart
        expected_events = [{'name': 'movie_server_0%d' % (idx + 1), 'state': 20}
                           for idx in range(3)]
        received_events = self.evloop.wait_until_events(self.evloop.event_queue, expected_events, 10)
        self.assertEqual(3, len(received_events))
        self.assertEqual([], expected_events)
        # check final status
        ending_status = self._get_movie_servers()
        # expecting initial status
        self.assertDictEqual(self.running_processes, ending_status)

    def _check_conciliation_user_database(self, conciliation):
        """ Test a conciliation strategy on USER request. """
        # empty all queues
        self.evloop.flush()
        # create the conflicts and check the events received
        self._create_database_conflicts()
        # check the conflicts and the CONCILIATION status using RPC
        self._check_database_conflicts()
        # use the conciliation function in parameter
        conciliation()
        # check supvisors event: OPERATION state is expected
        event = self._get_next_supvisors_event()
        self.assertEqual('OPERATION', event['statename'])
        # check that there is no conflict anymore
        self._check_no_conflict()

    def _check_conciliation_user_running_failure(self):
        """ Test the RUNNING_FAILURE conciliation on USER request. """
        print('### [INFO] Testing USER - RUNNING_FAILURE conciliation')
        # empty all queues
        self.evloop.flush()
        # create the conflicts and check the events received
        self._create_manager_conflicts()
        # check the conflicts and the CONCILIATION status using RPC
        self._check_manager_conflicts()
        # conciliate the conflicts using strategy
        self.local_supvisors.conciliate(ConciliationStrategies.RUNNING_FAILURE.value)
        # the my_movies application is expected to restart
        # => 3 manager + 1 hmi to stop
        expected_events = [{'name': 'manager', 'state': 0, 'address': address}
                           for address in self.running_addresses]
        expected_events.append({'name': 'hmi', 'state': 0})
        received_events = self.evloop.wait_until_events(self.evloop.event_queue, expected_events, 10)
        self.assertEqual(4, len(received_events))
        self.assertEqual([], expected_events)
        # 3 processes to start (one FATAL)
        # => 1 manager + 1 FATAL web_server + 1 hmi to start
        expected_events = [{'name': 'manager', 'state': 20},
                           {'name': 'web_server', 'state': 200},
                           {'name': 'hmi', 'state': 20}]
        received_events = self.evloop.wait_until_events(self.evloop.event_queue, expected_events, 10)
        self.assertEqual(3, len(received_events))
        self.assertEqual([], expected_events)
        # check supvisors event: OPERATION state is expected
        event = self._get_next_supvisors_event()
        self.assertEqual('OPERATION', event['statename'])
        # check that there is no conflict anymore
        self._check_no_conflict()

    def _check_no_conflict(self):
        """ Check that there is no conflict. """
        # test that Supvisors is in OPERATION state
        state = self.local_supvisors.get_supvisors_state()
        self.assertEqual('OPERATION', state['statename'])
        # test that Supvisors conflicts is empty
        self.assertEqual([], self.local_supvisors.get_conflicts())

    def _create_database_conflicts(self):
        """ Create conflicts on database application. """
        # start all movie_server programs on all addresses
        for address, proxy in self.proxies.items():
            for idx in range(3):
                try:
                    program = 'movie_server_0%d' % (idx + 1)
                    proxy.supervisor.startProcess('database:' + program)
                except xmlrpclib.Fault as exc:
                    self.assertEqual(Faults.ALREADY_STARTED, exc.faultCode)
                else:
                    # confirm starting through events
                    event = self._get_next_process_event()
                    self.assertDictContainsSubset({'name': program, 'state': 10, 'address': address}, event)
                    event = self._get_next_process_event()
                    self.assertDictContainsSubset({'name': program, 'state': 20, 'address': address}, event)
        # check supvisors event: CONCILIATION state is expected
        event = self._get_next_supvisors_event()
        self.assertEqual('CONCILIATION', event['statename'])

    def _check_database_conflicts(self):
        """ Test conflicts on database application using XML-RPC. """
        # check that the conflicts are detected in all Supvisors instances
        for proxy in self.proxies.values():
            # test that Supvisors is in CONCILIATION state (in all instances)
            state = proxy.supvisors.get_supvisors_state()
            self.assertEqual('CONCILIATION', state['statename'])
            # test Supvisors conflicts
            conflicts = proxy.supvisors.get_conflicts()
            process_names = [proc['process_name'] for proc in conflicts]
            self.assertItemsEqual(process_names, ['movie_server_01', 'movie_server_02', 'movie_server_03'])

    def _create_manager_conflicts(self):
        """ Create conflicts on the my_movies:manager process. """
        # start the manager program on all addresses
        for address, proxy in self.proxies.items():
            try:
                proxy.supervisor.startProcess('my_movies:manager')
            except xmlrpclib.Fault as exc:
                self.assertEqual(Faults.ALREADY_STARTED, exc.faultCode)
            else:
                # confirm starting through events
                event = self._get_next_process_event()
                self.assertDictContainsSubset({'name': 'manager', 'state': 10, 'address': address}, event)
                event = self._get_next_process_event()
                self.assertDictContainsSubset({'name': 'manager', 'state': 20, 'address': address}, event)
        # check supvisors event: CONCILIATION state is expected
        event = self._get_next_supvisors_event()
        self.assertEqual('CONCILIATION', event['statename'])

    def _check_manager_conflicts(self):
        """ Test conflicts on the my_movies:manager process using RPC. """
        # check that the conflicts are detected in all Supvisors instances
        for proxy in self.proxies.values():
            # test that Supvisors is in CONCILIATION state (in all instances)
            state = proxy.supvisors.get_supvisors_state()
            self.assertEqual('CONCILIATION', state['statename'])
            # test Supvisors conflicts
            conflicts = proxy.supvisors.get_conflicts()
            process_names = [proc['process_name'] for proc in conflicts]
            self.assertItemsEqual(process_names, ['manager'])

    def _get_movie_servers(self):
        """ Get the running status of the movie_server_0x processes. """
        process_info = self.local_supvisors.get_process_info('database:*')
        running_processes = {info['process_name']: info['addresses']
                             for info in process_info
                             if info['statecode'] == ProcessStates.RUNNING}
        return running_processes


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Check the Supvisors conciliation strategies.')
    parser.add_argument('-p', '--port', type=int, default=60002,
                        help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
