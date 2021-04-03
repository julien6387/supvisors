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

import os
import zmq

from queue import Empty
from socket import gethostname
from supervisor import childutils

from supvisors import rpcrequests
from supvisors.ttypes import AddressStates
from supvisors.client.subscriber import create_logger
from supvisors.tests.base import CompatTestCase

from scripts.event_queues import SupvisorsEventQueues


class RunningAddressesTest(CompatTestCase):
    """ Intermediate layer for the check of initial conditions:
        - 3 running addresses.

    Proxies to XML-RPC servers are opened.
    The thread of Event queues is started.
    """

    def setUp(self):
        """ Check that 3 running addresses are available. """
        # get a reference to the local RPC proxy
        self.local_proxy = childutils.getRPCInterface(os.environ)
        self.local_supervisor = self.local_proxy.supervisor
        self.local_supvisors = self.local_proxy.supvisors
        # check the number of running addresses
        addresses_info = self.local_supvisors.get_all_addresses_info()
        self.running_addresses = [info['address_name']
                                  for info in addresses_info
                                  if info['statecode'] == AddressStates.RUNNING.value]
        self.assertEqual(3, len(self.running_addresses))
        # assumption is made that this test is run on Supvisors Master address
        self.assertEqual(gethostname(), self.local_supvisors.get_master_address())
        # keep a reference to all RPC proxies
        self.proxies = {address: rpcrequests.getRPCInterface(address, os.environ)
                        for address in self.running_addresses}
        # create the thread of event subscriber
        self.zcontext = zmq.Context.instance()
        self.logger = create_logger(logfile=r'./log/running_addresses.log')
        self.evloop = SupvisorsEventQueues(self.zcontext, self.logger)
        # start the thread
        self.evloop.start()
        self.logger.info('Event loop created')

    def tearDown(self):
        """ The tearDown stops the subscriber to the Supvisors events. """
        self.evloop.stop()
        self.evloop.join()
        self.logger.info('Event loop ended')
        # close resources
        self.logger.close()
        self.zcontext.term()

    def _get_next_supvisors_event(self, timeout=15):
        """ Return next Supvisors status from queue. """
        try:
            return self.evloop.supvisors_queue.get(True, timeout)
        except Empty:
            self.fail('failed to get the expected Supvisors status')

    def _get_next_application_status(self, timeout=2):
        """ Return next Application status from queue. """
        try:
            return self.evloop.application_queue.get(True, timeout)
        except Empty:
            self.fail('failed to get the expected Application status')

    def _get_next_process_event(self, timeout=10):
        """ Return next Process event from queue. """
        try:
            return self.evloop.event_queue.get(True, timeout)
        except Empty:
            self.fail('failed to get the expected Process event')
