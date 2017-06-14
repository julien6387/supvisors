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

import os
import sys
import unittest

from socket import gethostname

from supervisor import childutils
from supervisor.states import ProcessStates

from supvisors import rpcrequests
from supvisors.ttypes import AddressStates, SupvisorsStates


class SupvisorsTest(unittest.TestCase):
    """ Intermediate layer for the check of initial conditions:
    - 3 running addresses,
    - one movie_server running on each address. """

    def setUp(self):
        """ Check that 3 addresses are available. """
        # get a reference to the local RPC proxy
        local_proxy = childutils.getRPCInterface(os.environ)
        # check the number of running addresses
        addresses_info = local_proxy.supvisors.get_all_addresses_info()
        self.running_addresses = [info['address_name'] for info in addresses_info
            if info['statecode'] == AddressStates.RUNNING]
        self.assertEqual(3, len(self.running_addresses))
        # assumption is made that this test is run on Supvisors Master address
        self.assertEqual(gethostname(), local_proxy.supvisors.get_master_address())
        # keep a reference to all RPC proxies
        self.proxies = {address: rpcrequests.getRPCInterface(address, os.environ)
            for address in self.running_addresses}
        # store initial process status
        process_info = local_proxy.supvisors.get_process_info('database:*')
        self.running_processes = {info['process_name']: info['addresses']
            for info in process_info if info['statecode'] == ProcessStates.RUNNING}
        self.assertItemsEqual(self.running_processes.keys(),
            ['movie_server_01', 'movie_server_02', 'movie_server_03'])
        addresses = [address for addresses in self.running_processes.values()
            for address in addresses]
        self.assertSetEqual(set(self.running_addresses), set(addresses))


class ConciliationTest(SupvisorsTest):
    """ Test case to check the conciliation of Supvisors.
    TODO: add RPC for set conciliation strategy.
        => impact on rpcinterface, supvisorsctl, client java, docs.
    The aim is to test user and auto conciliation, depending on the configuration.
    """

    def setUp(self):
        """ Test the conciliation after creating conflicts. """
        # TODO: install listener
        # check that there is no conflict before to start testing
        self._check_no_conflict()
        # create the conflicts
        self._create_database_conflicts()

    def test_conciliation(self):
        """ Check depending on the configuration. """

    def test_conciliation_senicide(self):
        """ Test the conciliation after creating conflicts. """
        self._create_database_conflicts()
        # test change of Supvisors state OPERATION -> CONCILIATION -> OPERATION

    def test_conciliation_infanticide(self):
        """ Test the conciliation after creating conflicts. """
        # TODO: set the strategy to INFANTICIDE (how ???)
        # create the conflicts
        self._create_database_conflicts()
        # check the Supvisors state transitions
        # check that there is no conflict anymore

    def test_conciliation_user(self):
        """ Test the conciliation after creating conflicts. """
        # TODO: set the strategy to USER
        # check that there is no conflict anymore
        self._check_no_conflict()
        # create the conflicts and check the CONCILIATION status
        self._create_database_conflicts()
        self._check_database_conflicts()
        # conciliate the conflicts with RPC requests
        for process, addresses in self.running_processes:
            for address in self.running_addresses - addresses:
                self.proxies[address].supervisor.stopProcess(process)
        # TBC: wait for next tick ?
        # check that there is no conflict anymore
        self._check_no_conflict()

    def _check_no_conflict(self):
        """ Check that there is no conflict at present. """
        for proxy in self.proxies:
            # test that Supvisors is in OPERATION state
            supvisors_state = proxy.supvisors.get_supvisors_state()
            self.assertEqual(SupvisorsStates.OPERATION, supvisors_state['statecode'])
            # test that Supvisors conflicts is empty
            self.assertEqual([], proxy.supvisors.get_conflicts())

    def _create_database_conflicts(self):
        """ Create conflicts on database application. """
        # start all movie_server programs on all addresses
        # TBC: need to catch exception ?
        for proxy in self.proxies:
            proxy.supervisor.startProcess('database:movie_server_01')
            proxy.supervisor.startProcess('database:movie_server_02')
            proxy.supervisor.startProcess('database:movie_server_03')

    def _check_database_conflicts(self):
        """ Test conflicts on database application. """
        # check that the conflicts are detected in all Supvisors instances
        for proxy in self.proxies:
            # test that Supvisors is in CONCILIATION state
            supvisors_state = proxy.supvisors.get_supvisors_state()
            self.assertEqual(SupvisorsStates.CONCILIATION, supvisors_state['statecode'])
            # test Supvisors conflicts
            conflicts = proxy.supvisors.get_conflicts()
            process_names = [proc['process_name'] for proc in conflicts]
            self.assertItemsEqual(process_names,
                ['movie_server_01', 'movie_server_02', 'movie_server_03'])


class RunningFailureTest(SupvisorsTest):
    """ Test case to check the running failure strategies of Supvisors. """

    def test_running_failure(self):
        """ Test the running failure strategy. """


class LoadingTest(SupvisorsTest):
    """ Test case to check the loading strategies of Supvisors. """

    def test_loading(self):
        """ Test the starting strategies iaw the rules defined. """


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
