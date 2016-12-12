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
import unittest
from Queue import Empty, Queue

from supervisor.childutils import getRPCInterface
from supervisor.options import make_namespec

from supervisors.client.subscriber import *


class SupervisorsEventQueues(SupervisorsEventInterface):
    """ The SupervisorsEventQueues is a python thread that connects to Supervisors
    and stores the application and process events received into queues. """

    def __init__(self, port, logger):
        """ Initialization of the attributes. """
        SupervisorsEventInterface.__init__(self, create_zmq_context(), port, logger)
        # create a set of addresses
        self.addresses = set()
        # create queues to store messages
        self.event_queues = (Queue(), Queue(), Queue())
        # subscribe to address status only
        self.subscriber.subscribe_address_status()
        # test relies on 3 addresses so theoretically, we only need 3 notifications
        # to know which address is RUNNING or not
        # work on 5 notifications, just in case.
        # the startsecs of the ini file of this program is then set to 30 seconds
        self.nb_address_notifications = 0
 
    def on_address_status(self, data):
        """ Pushes the AddressStatus message into a queue. """
        self.logger.info('got AddressStatus message: {}'.format(data))
        if data['statename'] == 'RUNNING':
            self.addresses.add(data['address_name'])
        # check the number of notifications
        self.nb_address_notifications += 1
        if self.nb_address_notifications == 5:
            self.logger.info('addresses: {}'.format(self.addresses))
            # got all notification, unsubscribe from AddressStatus
            self.subscriber.unsubscribe_address_status()
            # subscribe to application and process status
            self.subscriber.subscribe_application_status()
            self.subscriber.subscribe_process_status()
            # notify CheckSequence with an event in start_queue
            self.event_queues[0].put(self.addresses)

    def on_application_status(self, data):
        """ Pushes the ApplicationStatus message into a queue. """
        self.logger.info('got ApplicationStatus message: {}'.format(data))
        self.event_queues[1].put(data)

    def on_process_status(self, data):
        """ Pushes the ProcessStatus message into a queue. """
        self.logger.info('got ProcessStatus message: {}'.format(data))
        self.event_queues[2].put(data)


class CheckSequenceTest(unittest.TestCase):
    """ Test case to check the sequencing of the test application. """

    PORT = 60002

    def setUp(self):
        """ The setUp starts the subscriber to the Supervisors events and get the event queues. """
        # create logger using a BoundIO
        self.logger = create_logger(logfile=None)
        # create the thread of event subscriber
        self.event_loop = SupervisorsEventQueues(self.PORT, self.logger)
        # get the queues
        self.address_queue = self.event_loop.event_queues[0]
        self.application_queue = self.event_loop.event_queues[1]
        self.process_queue = self.event_loop.event_queues[2]
        # start the thread
        self.event_loop.start()

    def tearDown(self):
        """ The tearDown stops the subscriber to the Supervisors events. """
        self.event_loop.stop()
        self.event_loop.join()

    def test_sequencing(self):
        """ Test the whole sequencing of the starting of the test application.
        At this point, Supervisors is in DEPLOYMENT phase.
        This process is the first to be started. """
        # wait for start_queue to trigger
        self.get_addresses()
        # test the last events received for this process
        self.check_self_starting()
        # test the starting of database application
        self.check_database_starting()
        # test the starting of my_movies application
        self.check_my_movies_starting()
        # test the starting of web_movies application
        self.check_web_movies_starting()

    def check_database_starting(self):
        """ Check the starting of the database application.
        The movie_server_xx processes are started first, then the register_movies_xx.
        In the database application, there should not be any major_failure but the minor_failure is raised
        if one program is FATAL. """
        self.major_failure = False
        self.minor_failure = False
        # get database rules
        rules = getRPCInterface(os.environ).supervisors.get_process_rules('database:*')
        self.rules = {rule['namespec']: rule['addresses'] for rule in rules}
        # first group contains the movie_server_xx programs
        self.check_movie_server_starting()
        # second group contains the register_movie_xx programs
        self.check_register_movies_starting()

    def check_movie_server_starting(self):
        """ Check the starting of the movie_server programs.
        The first phase consists in testing that the movie_server_xx processes are STARTING or FATAL,
        depending on the addresses available.
        The dabase application should be STOPPED until one process becomes STARTING.
        The second phase consists in testing that the movie_server_xx processes that were STARTING
        in the first phase become RUNNING.
        The dabase application become RUNNING when there is no more STARTING process. """
        self.process_list = ['movie_server_01', 'movie_server_02', 'movie_server_03']
        self.starting_processes = []
        # check processes are STARTING / RUNNING or FATAL
        self.check_process_starting('database', 0, 'STOPPED')
        self.check_process_running('database', 2) # startsecs=1

    def check_register_movies_starting(self):
        """ Check the starting of the register_movies programs.
        The first phase consists in testing that the register_movies_xx processes are STARTING or FATAL,
        depending on the addresses available.
        The dabase application should transition from RUNNING to STARTING.
        The second phase consists in testing that the register_movies_xx processes that were STARTING
        in the first phase become RUNNING.
        The dabase application should become RUNNING when there is no more STARTING process. """
        self.process_list = ['register_movies_01', 'register_movies_02', 'register_movies_03']
        self.starting_processes = []
        # check processes are STARTING / RUNNING or FATAL
        self.check_process_starting('database', 2, 'RUNNING')
        # copy starting_processes as the same list is to be used for exited processes
        starting_processes_copy = [process_name for process_name, addresses in self.starting_processes]
        self.check_process_running('database', 2) # startsecs=1
        self.starting_processes = starting_processes_copy
        self.check_process_exited('database', 5) # -x 5

    def check_my_movies_starting(self):
        """ Check the starting of the my_movies application.
        The manager process is started first, then the hmi.
        In the my_movies application, there should be not any major_failure or minor_failure. """
        self.major_failure = False
        self.minor_failure = False
        # get database rules
        rules = getRPCInterface(os.environ).supervisors.get_process_rules('my_movies:*')
        self.rules = {rule['namespec']: rule['addresses'] for rule in rules}
        # first group contains the manager program
        self.check_manager_starting()
        # second group contains the hmi program
        self.check_hmi_starting()

    def check_manager_starting(self):
        """ Check the starting of the manager program.
        The first phase consists in testing that the manager process is STARTING, whatever the active addresses.
        The my_movies application should become STARTING.
        The second phase consists in testing that the manager process becomes RUNNING.
        The my_movies application should become RUNNING. """
        self.process_list = ['manager']
        self.starting_processes = []
        # check processes are STARTING / RUNNING
        self.check_process_starting('my_movies', 0, 'STOPPED')
        self.check_process_running('my_movies', 1) # startsecs=0

    def check_hmi_starting(self):
        """ Check the starting of the hmi program.
        The first phase consists in testing that the hmi process is STARTING, whatever the active addresses.
        The my_movies application should become STARTING.
        The second phase consists in testing that the hmi process becomes RUNNING.
        The my_movies application should become RUNNING. """
        self.process_list = ['hmi']
        self.starting_processes = []
        # check processes are STARTING / RUNNING
        self.check_process_starting('my_movies', 2, 'RUNNING')
        self.check_process_running('my_movies', 3) # startsecs=2

    def check_web_movies_starting(self):
        """ Check the starting of the web_movies application.
        The web_server process is started first, then the web_browser.
        In the web_movies application, there should not be any major_failure or minor_failure. """
        self.major_failure = False
        self.minor_failure = False
        # get database rules
        rules = getRPCInterface(os.environ).supervisors.get_process_rules('web_movies:*')
        self.rules = {rule['namespec']: rule['addresses'] for rule in rules}
        # first group contains the manager program
        self.check_web_server_starting()
        # second group contains the hmi program
        self.check_web_browser_starting()

    def check_web_server_starting(self):
        """ Check the starting of the web_server program.
        The first phase consists in testing that the web_server process is STARTING, whatever the active addresses.
        The web_movies application should become STARTING.
        The second phase consists in testing that the web_server process becomes RUNNING.
        The web_movies application should become RUNNING. """
        self.process_list = ['web_server']
        self.starting_processes = []
        # check processes are STARTING / RUNNING
        self.check_process_starting('web_movies', 0, 'STOPPED')
        self.check_process_running('web_movies', 6) # startsecs=5

    def check_web_browser_starting(self):
        """ Check the starting of the web_browser program.
        The first phase consists in testing that the web_browser process is STARTING, whatever the active addresses.
        The web_movies application should become STARTING.
        The second phase consists in testing that the web_browser process becomes RUNNING.
        The web_movies application should become RUNNING. """
        self.process_list = ['web_browser']
        self.starting_processes = []
        # check processes are STARTING / RUNNING
        self.check_process_starting('web_movies', 2, 'RUNNING')
        self.check_process_running('web_movies', 1) # startsecs=0

    def check_process_starting(self, application_name, ref_application_statecode, ref_application_statename):
        """ Check that the processes listed in self.process_list become STARTING or FATAL,
        depending on the active addresses.
        The application state becomes STARTING when there is at least one STARTING process. """
        for _ in range(len(self.process_list)):
            # get next process event
            try:
                data = self.process_queue.get(True, 2)
            except Empty:
                self.fail('failed to get the expected events for this process')
            else:
                process_name = data['process_name']
                self.assertEqual(application_name, data['application_name'])
                # check that process name is in list and remove it from the list
                self.assertIn(process_name, self.process_list)
                self.process_list.remove(process_name)
                # build namespec from process and application names
                namespec = make_namespec(application_name, process_name)
                # get intersection between rules and valid addresses
                applicable_addresses = self.addresses if self.rules[namespec] == ['*'] else set(self.rules[namespec]).intersection(self.addresses)
                # check that process can be started on an active address
                if applicable_addresses:
                    self.assertEqual('STARTING', data['statename'])
                    self.assertEqual(1, len(data['addresses']))
                    self.assertIn(data['addresses'][0], applicable_addresses)
                    # store in starting processes
                    self.starting_processes.append((process_name, data['addresses']))
                else:
                    self.assertEqual('FATAL', data['statename'])
                    self.assertFalse(data['addresses'])
                    self.minor_failure = True
            # get next application event
            try:
                data = self.application_queue.get(True, 1)
            except Empty:
                self.fail('failed to get the expected events for this process')
            else:
                # application is in ref_application_statename until one process is STARTING
                self.assertEqual(application_name, data['application_name'])
                self.assertEqual(1 if self.starting_processes else ref_application_statecode, data['statecode'])
                self.assertEqual('STARTING' if self.starting_processes else ref_application_statename, data['statename'])
                self.assertEqual(self.major_failure, data['major_failure'])
                self.assertEqual(self.minor_failure and data['statename'] != 'STOPPED', data['minor_failure'])

    def check_process_running(self, application_name, startsecs):
        """ Check that the processes listed in self.starting_processes become RUNNING.
        The application state becomes RUNNING when there is no more STARTING process. """
        for _ in range(len(self.starting_processes)):
            # get next process event
            try:
                data = self.process_queue.get(True, startsecs)
            except Empty:
                self.fail('failed to get the expected events for this process')
            else:
                process_name = data['process_name']
                self.assertEqual(application_name, data['application_name'])
                # check that process name is in list and remove it from the list
                self.assertIn((process_name, data['addresses']), self.starting_processes)
                self.starting_processes.remove((process_name, data['addresses']))
                # build namespec from process and application names
                self.assertEqual('RUNNING', data['statename'])
            # get next application event
            try:
                data = self.application_queue.get(True, 1)
            except Empty:
                self.fail('failed to get the expected events for this process')
            else:
                # application is STARTING until all processes are RUNNING
                self.assertEqual(application_name, data['application_name'])
                self.assertEqual(1 if self.starting_processes else 2, data['statecode'])
                self.assertEqual('STARTING' if self.starting_processes else 'RUNNING', data['statename'])
                self.assertEqual(self.major_failure, data['major_failure'])
                self.assertEqual(self.minor_failure, data['minor_failure'])

    def check_process_exited(self, application_name, duration):
        """ Check that the processes listed in self.starting_processes become EXITED.
        The application state is always RUNNING. """
        for _ in range(len(self.starting_processes)):
            # get next process event
            try:
                data = self.process_queue.get(True, duration)
            except Empty:
                self.fail('failed to get the expected EXITED events for the processes of the application {}'.format(application_name))
            else:
                self.assertEqual(application_name, data['application_name'])
                # check that process name is in list and remove it from the list
                self.assertIn(data['process_name'], self.starting_processes)
                self.starting_processes.remove(data['process_name'])
                self.assertFalse(data['addresses'])
                self.assertTrue(data['expected_exit'])
                # build namespec from process and application names
                self.assertEqual('EXITED', data['statename'])
            # get next application event
            try:
                data = self.application_queue.get(True, 1)
            except Empty:
                self.fail('failed to get the expected events for the application {}'.format(application_name))
            else:
                # application is RUNNING
                self.assertDictContainsSubset({'application_name': application_name,
                    'statecode': 2, 'statename': 'RUNNING'}, data)
                self.assertEqual(self.major_failure, data['major_failure'])
                self.assertEqual(self.minor_failure, data['minor_failure'])

    def check_self_starting(self):
        """ Test the events received that corresponds to the starting of this process. """
        try:
            # this process has a startsecs of 30 seconds
            # depending on the active addresses and timing considerations, the 5 notifications can be received between 5 and 25 seconds
            # so, in the 'worst' case, it may take 25 seconds before the RUNNING event is received
            data = self.process_queue.get(True, 26)
            # test that this process is RUNNING
            self.assertDictContainsSubset({'process_name': 'check_start_sequence',
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
            self.addresses = self.address_queue.get(True, 30)
            self.assertGreater(len(self.addresses), 0)
        except Empty:
            self.fail('failed to get the address event in the last 30 seconds')


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Check the starting sequence using Supervisors events.')
    parser.add_argument('-p', '--port', type=int, default=60002, help="the event port of Supervisors")
    args = parser.parse_args()
    CheckSequenceTest.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')

