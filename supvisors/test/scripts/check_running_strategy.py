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

from queue import Empty

from supvisors.ttypes import StartingStrategies

from scripts.event_queues import SupvisorsEventQueues
from scripts.running_addresses import RunningAddressesTest


class RunningFailureStrategyTest(RunningAddressesTest):
    """ Test case to check the running failure strategies of Supvisors. """

    def setUp(self):
        """ Used to swallow process events related to this process. """
        # call parent
        RunningAddressesTest.setUp(self)
        # as this process has just been started, STARTING / RUNNING events
        # might be received
        # other events may be triggered from tearDown too
        has_events = True
        while has_events:
            try:
                self.evloop.event_queue.get(True, 8)
            except Empty:
                # no more events: exit
                has_events = False
            try:
                self.evloop.application_queue.get(True, 2)
                has_events = True
            except Empty:
                # no more events: exit
                has_events = False

    def tearDown(self):
        """ The tearDown restarts the processes that may have been stopped,
        in accordance with initial configuration. """
        try:
            self.local_supvisors.start_process(StartingStrategies.CONFIG,
                                               'database:movie_server_01')
        except:
            # exception is expected if process already running
            pass
        try:
            self.local_supvisors.start_process(StartingStrategies.CONFIG,
                                               'web_movies:web_browser')
        except:
            # exception is expected if process already running
            pass
        try:
            self.local_supvisors.start_application(StartingStrategies.CONFIG,
                                                   'my_movies')
        except:
            # exception is expected if application already running
            pass
        # call parent
        RunningAddressesTest.tearDown(self)

    def test_continue(self):
        """ Test the CONTINUE running failure strategy. """
        print('### Testing CONTINUE running failure strategy')
        # force the movie_server_01 to exit with a fake segmentation fault
        self.local_supervisor.signalProcess('database:movie_server_01',
                                            'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'movie_server_01',
                                       'expected': False,
                                       'state': 100}, event)
        # application should be still running with 2 other movie servers,
        # but with minor failure
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'database',
                                       'major_failure': False,
                                       'minor_failure': True,
                                       'statename': 'RUNNING'}, event)
        # no further event expected
        with self.assertRaises(Empty):
            self.evloop.event_queue.get(True, 5)
        with self.assertRaises(Empty):
            self.evloop.application_queue.get(True, 2)

    def test_restart_process(self):
        """ Test the RESTART_PROCESS running failure strategy. """
        print('### Testing RESTART_PROCESS running failure strategy')
        # force the web_browser to exit with a fake segmentation fault
        self.local_supervisor.signalProcess('web_movies:web_browser',
                                            'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'web_browser',
                                       'expected': False,
                                       'state': 100}, event)
        # application should be stopped: no more process running
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'web_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'STOPPED'}, event)
        # STARTING / RUNNING events are expected for this process
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'web_browser',
                                       'state': 10}, event)
        # application should be starting
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'web_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'STARTING'}, event)
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'web_browser',
                                       'state': 20}, event)
        # application should be running
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'web_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'RUNNING'}, event)
        # no further event expected
        with self.assertRaises(Empty):
            self.evloop.event_queue.get(True, 5)
        with self.assertRaises(Empty):
            self.evloop.application_queue.get(True, 2)

    def test_stop_application(self):
        """ Test the STOP_APPLICATION running failure strategy. """
        print('### Testing STOP_APPLICATION running failure strategy')
        # get the hmi running location
        infos = self.local_supvisors.get_process_info('my_movies:hmi')
        hmi_info = infos[0]
        self.assertEqual('RUNNING', hmi_info['statename'])
        self.assertEqual(1, len(hmi_info['addresses']))
        hmi_address = hmi_info['addresses'][0]
        # force the hmi to exit with a fake segmentation fault
        hmi_proxy = self.proxies[hmi_address].supervisor
        hmi_proxy.signalProcess('my_movies:hmi', 'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'hmi',
                                       'expected': False,
                                       'state': 100}, event)
        # application should be still running with manager,
        # but with major failure due to web_server that cannot be started,
        # and with minor failure due to hmi crash
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': True,
                                       'statename': 'RUNNING'}, event)
        # STOPPING / STOPPED events are expected for the manager
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'manager',
                                       'state': 40}, event)
        # application should be stopping
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'STOPPING'}, event)
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'manager',
                                       'state': 0}, event)
        # application should be stopped
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'STOPPED'}, event)
        # no further event expected
        with self.assertRaises(Empty):
            self.evloop.event_queue.get(True, 5)
        with self.assertRaises(Empty):
            self.evloop.application_queue.get(True, 2)

    def test_restart_application(self):
        """ Test the RESTART_APPLICATION running failure strategy. """
        print('### Testing RESTART_APPLICATION running failure strategy')
        # get the manager running location
        infos = self.local_supvisors.get_process_info('my_movies:manager')
        manager_info = infos[0]
        self.assertEqual('RUNNING', manager_info['statename'])
        self.assertEqual(1, len(manager_info['addresses']))
        manager_address = manager_info['addresses'][0]
        # force the manager to exit with a fake segmentation fault
        manager_proxy = self.proxies[manager_address].supervisor
        manager_proxy.signalProcess('my_movies:manager', 'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'manager',
                                       'expected': False,
                                       'state': 100}, event)
        # application should be still running with hmi but with major failure
        # because of required manager and web_server that are not running
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': False,
                                       'statename': 'RUNNING'}, event)
        # STOPPING / STOPPED events are expected for the hmi
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'hmi',
                                       'state': 40}, event)
        # application should be stopping
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'STOPPING'}, event)
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'hmi',
                                       'state': 0}, event)
        # application should be stopped
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': False,
                                       'minor_failure': False,
                                       'statename': 'STOPPED'}, event)
        # STARTING / RUNNING events are expected for the manager
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'manager',
                                       'state': 10}, event)
        # application should be starting, with major failure because of
        # required web_server that is not started yet
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': False,
                                       'statename': 'STARTING'}, event)
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'manager',
                                       'state': 20}, event)
        # application should be running, with major failure because of
        # required web_server that is not started yet
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': False,
                                       'statename': 'RUNNING'}, event)
        # FATAL event is expected for the web_server
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'web_server',
                                       'state': 200}, event)
        # application should be still running, with major failure because of
        # web_server that cannot be started
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': False,
                                       'statename': 'RUNNING'}, event)
        # STARTING / RUNNING events are expected for the hmi
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'hmi',
                                       'state': 10}, event)
        # application should be starting, with major failure because of
        # web_server that cannot be started
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': False,
                                       'statename': 'STARTING'}, event)
        event = self._get_next_process_event()
        self.assertDictContainsSubset({'name': 'hmi',
                                       'state': 20}, event)
        # application should be running, with major failure because of
        # web_server that cannot be started
        event = self._get_next_application_status()
        self.assertDictContainsSubset({'application_name': 'my_movies',
                                       'major_failure': True,
                                       'minor_failure': False,
                                       'statename': 'RUNNING'}, event)
        # no further event expected
        with self.assertRaises(Empty):
            self.evloop.event_queue.get(True, 5)
        with self.assertRaises(Empty):
            self.evloop.application_queue.get(True, 2)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    # get arguments
    import argparse

    parser = argparse.ArgumentParser(
        description='Check the Supvisors running failure strategies.')
    parser.add_argument('-p', '--port', type=int, default=60002,
                        help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
