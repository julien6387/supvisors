#!/usr/bin/python
#-*- coding: utf-8 -*-

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

import os
import signal
import sys
import unittest
from Queue import Empty

from supervisor.childutils import getRPCInterface

from supvisors.client.subscriber import *
from supvisors.test.scripts.event_queue import SupvisorsEventQueues


class CheckStopSequenceTest(unittest.TestCase):
    """ Test case to check the sequencing of the stopping test application. """

    PORT = 60002

    def setUp(self):
        """ The setUp starts the subscriber to the Supvisors events and get the event queues. """
        # create logger using a BoundIO
        self.logger = create_logger(logfile=None)
        # create the thread of event subscriber
        self.event_loop = SupvisorsEventQueues(self.PORT, self.logger)
        # one single notification is required to set the subscriptions
        self.event_loop.nb_address_notifications = 4
        # get the queues
        self.address_queue = self.event_loop.event_queues[0]
        self.application_queue = self.event_loop.event_queues[1]
        self.process_queue = self.event_loop.event_queues[2]
        # start the thread
        self.event_loop.start()
        # get a supvisors proxy
        self.proxy = getRPCInterface(os.environ)

    def tearDown(self):
        """ The tearDown stops the subscriber to the Supvisors events. """
        self.event_loop.stop()
        self.event_loop.join()

    def test_sequencing(self):
        """ Test the whole sequencing of the starting of the test application.
        At this point, Supvisors is in OPERATION phase.
        This process is the first to be started. """
        # wait for address_queue to trigger
        self.get_addresses()
        # start a converter
        self.proxy.supvisors.start_args('my_movies:converter_05')
        # get all running processes
        self.update_running_list()
        # empty queues (pull STARTING / RUNNING events)
        self.check_converter_running()
        # send restart request
        self.proxy.supvisors.restart()
        # test the starting of web_movies application
        self.check_application_stopping('web_movies')
        # test the starting of my_movies application
        self.check_application_stopping('my_movies')
        # test the starting of database application
        self.check_application_stopping('database')
        # cannot test the last events received for this process

    def check_converter_running(self):
        try:
            # get next process event
            data = self.process_queue.get(True, 2)
            # quick check of event
            self.assertEqual('my_movies', data['application_name'])
            self.assertEqual('converter_05', data['process_name'])
            self.assertEqual('STARTING', data['statename'])
            # get next application event
            data = self.application_queue.get(True, 1)
            # quick check of event
            self.assertEqual('my_movies', data['application_name'])
            self.assertEqual('STARTING', data['statename'])
            # get next process event
            data = self.process_queue.get(True, 3)
             # quick check of event
            self.assertEqual('my_movies', data['application_name'])
            self.assertEqual('converter_05', data['process_name'])
            self.assertEqual('RUNNING', data['statename'])
            # get next application event
            data = self.application_queue.get(True, 1)
            # quick check of event
            self.assertEqual('my_movies', data['application_name'])
            self.assertEqual('RUNNING', data['statename'])
        except Empty:
            self.fail('failed to get the expected events for this process')

    def update_running_list(self):
        """ Store info and rules about the running processes of the application considered. """
        # get running processes
        info_list = self.proxy.supvisors.get_all_process_info()
        application_list = {info['application_name'] for info in info_list}
        self.all_running_list = {application_name:
            [info['process_name'] for info in info_list
                if info['statename'] in ['RUNNING', 'STARTING', 'BACKOFF'] and application_name == info['application_name']]
            for application_name in application_list}

    def update_info_and_rules(self, application_name):
        """ Store info and rules about the running processes of the application considered. """
        self.application_name = application_name
        # get stopping sequence
        rules_list = self.proxy.supvisors.get_process_rules(application_name + ':*')
        sequences = set(rules['stop_sequence'] for rules in rules_list)
        self.stopping_sequence = {sequence: [rules['process_name'] for rules in rules_list if rules['stop_sequence'] == sequence] for sequence in sequences}
        # get running list of application
        self.running_list = self.all_running_list.pop(application_name, None)

    def check_application_stopping(self, application_name):
        """ Check the stopping of the application. """
        self.update_info_and_rules(application_name)
        # check all programs sorted by stopping_sequence
        for seq, process_list in self.stopping_sequence.items():
            # keep only those that are running
            self.process_list =  [process_name for process_name in process_list if process_name in self.running_list]
            self.stopping_processes = []
            # twice the size because two events are expected for each process
            for _ in range(2 * len(self.process_list)):
                self.check_process_event()
                self.check_application_event()

    def check_process_event(self):
        """ Check that the processes listed in self.process_list become STOPPING, then STOPPED. """
        # get next process event
        try:
            data = self.process_queue.get(True, 11) # stopwaitsecs = 10
        except Empty:
            self.fail('failed to get the expected events for this process')
        # check data
        process_name = data['process_name']
        self.assertEqual(self.application_name, data['application_name'])
        if data['statecode'] == 40:
            # process is STOPPING
            self.assertEqual('STOPPING', data['statename'])
            # check that process name is in list and store in starting processes
            self.assertIn(process_name, self.process_list)
            self.process_list.remove(process_name)
            self.stopping_processes.append(process_name)
            # check that process can be started on an active address
            self.assertTrue(data['addresses'])
        elif data['statecode'] == 0:
            # process is STOPPED
            self.assertEqual('STOPPED', data['statename'])
            # check that process name is in list and remove it from the lists
            self.assertIn(process_name, self.stopping_processes)
            self.stopping_processes.remove(process_name)
            self.running_list.remove(process_name)
            # build namespec from process and application names
            self.assertFalse(data['addresses'])
        else:
            self.fail('unexpected event {}({}) for the process {}:{}'.format(data['statename'], data['statecode'],
                self.application_name, process_name))

    def check_application_event(self):
        """ Check that the application state becomes STOPPING when there is at least one STOPPING process
        and STOPPED when there is no more running and STOPPING process. """
        # get next application event
        try:
            data = self.application_queue.get(True, 1)
        except Empty:
            self.fail('failed to get the expected events for this process')
        # check data
        self.assertEqual(self.application_name, data['application_name'])
        # application is STOPPING until all running processes are STOPPED
        if self.stopping_processes:
            self.assertEqual(3, data['statecode'])
            self.assertEqual('STOPPING', data['statename'])
        elif self.running_list:
            self.assertEqual(2, data['statecode'])
            self.assertEqual('RUNNING', data['statename'])
        else:
            self.assertEqual(0, data['statecode'])
            self.assertEqual('STOPPED', data['statename'])
            self.assertFalse(data['major_failure'])
            self.assertFalse(data['minor_failure'])

    def check_self_starting(self):
        """ Test the events received that corresponds to the starting of this process. """
        try:
            # this process has a startsecs of 30 seconds
            # depending on the active addresses and timing considerations, the 5 notifications can be received between 5 and 25 seconds
            # so, in the 'worst' case, it may take 25 seconds before the RUNNING event is received
            data = self.process_queue.get(True, 26)
            # test that this process is RUNNING
            self.assertDictContainsSubset({'process_name': 'check_stop_sequence',
                'statecode': 20, 'statename': 'RUNNING', 'application_name': 'test'}, data)
            self.assertEqual(1, len(data['addresses']))
            self.assertIn(data['addresses'][0], self.addresses)
            # test that the application related to this process is RUNNING
            data = self.application_queue.get(True, 2)
            self.assertDictEqual(data, {'application_name': 'test',
                'statecode': 2, 'statename': 'RUNNING',
                'major_failure': False, 'minor_failure': False})
        except Empty:
            self.fail('failed to get the expected events for this process')

    def get_addresses(self):
        """ Wait for address_queue to put the list of active addresses. """
        try:
            self.address_queue.get(True, 6)
            # not used
        except Empty:
            self.fail('failed to get the address event in the last 6 seconds')


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    # catch supervisor termination signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Check the stopping sequence using Supvisors events.')
    parser.add_argument('-p', '--port', type=int, default=60002, help="the event port of Supvisors")
    args = parser.parse_args()
    CheckStopSequenceTest.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')

