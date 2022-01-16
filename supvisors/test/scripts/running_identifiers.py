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
import unittest

import zmq

from queue import Empty
from socket import gethostname
from supervisor.childutils import getRPCInterface

from supvisors.ttypes import SupvisorsInstanceStates
from supvisors.utils import SupervisorServerUrl
from supvisors.client.subscriber import create_logger

from .event_queues import SupvisorsEventQueues


class RunningIdentifiersTest(unittest.TestCase):
    """ Intermediate layer for the check of initial conditions:
        - 4 running instances.

    Proxies to XML-RPC servers are opened.
    The thread of Event queues is started.
    """

    def setUp(self):
        """ Check that 4 running instances are available. """
        # get a reference to the local RPC proxy
        self.local_proxy = getRPCInterface(os.environ)
        self.local_supervisor = self.local_proxy.supervisor
        self.local_supvisors = self.local_proxy.supvisors
        # check the number of running instances
        instances_info = self.local_supvisors.get_all_instances_info()
        self.running_identifiers = {info['identifier']: (info['node_name'], info['port'])
                                    for info in instances_info
                                    if info['statecode'] == SupvisorsInstanceStates.RUNNING.value}
        self.assertEqual(4, len(self.running_identifiers))
        # assumption is made that this test is run on Master Supvisors instance
        self.assertEqual(gethostname(), self.local_supvisors.get_master_identifier())
        # keep a reference to all RPC proxies
        supervisor_url = SupervisorServerUrl(os.environ.copy())
        self.proxies = {}
        for identifier, (node_name, port) in self.running_identifiers.items():
            supervisor_url.update_url(node_name, port)
            self.proxies[identifier] = getRPCInterface(supervisor_url.env)
        # create the thread of event subscriber
        self.zcontext = zmq.Context.instance()
        self.logger = create_logger(logfile=r'./log/running_identifiers.log')
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
