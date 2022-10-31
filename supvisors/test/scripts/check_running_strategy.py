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
from supervisor.states import ProcessStates
from supvisors.ttypes import StartingStrategies, SupvisorsStates

from .event_queues import SupvisorsEventQueues
from .running_identifiers import RunningIdentifiersTest


class RunningFailureStrategyTest(RunningIdentifiersTest):
    """ Test case to check the running failure strategies of Supvisors. """

    def setUp(self):
        """ Used to swallow process events related to this process. """
        # call parent
        RunningIdentifiersTest.setUp(self)
        # determine web_browser identifier
        info = self.local_supvisors.get_process_info('web_movies:web_browser')[0]
        if info['statecode'] != ProcessStates.RUNNING:
            print('[ERROR] web_movies:web_browser not RUNNING')
        self.web_browser_node_name = info['identifiers'][0]
        # as this process has just been started, STARTING / RUNNING events might be received
        # other events may be triggered from tearDown too
        has_events = True
        while has_events:
            has_events = False
            try:
                self.evloop.event_queue.get(True, 8)
                has_events |= True
            except Empty:
                pass
            try:
                self.evloop.application_queue.get(True, 2)
                has_events |= True
            except Empty:
                pass

    def tearDown(self):
        """ The tearDown restarts the processes that may have been stopped,
        in accordance with initial configuration. """
        try:
            self.local_supvisors.start_process(StartingStrategies.CONFIG, 'database:movie_server_01')
        except Exception:
            # exception is expected if process already running
            pass
        try:
            self.local_supvisors.start_application(StartingStrategies.CONFIG, 'my_movies')
        except Exception:
            # exception is expected if application already running
            pass
        # wait for the OPERATION state and flush
        supvisors_state = SupvisorsStates.OPERATION
        try:
            supvisors_state = self.local_supvisors.get_supvisors_state()['fsm_statename']
        except Exception:
            # exception is expected if application already running
            pass
        if supvisors_state != 'OPERATION':
            self.logger.info(f'wait for Supvisors to be in OPERATION state (current={supvisors_state})')
            self.evloop.wait_until_events(self.evloop.supvisors_queue, [{'fsm_statename': 'OPERATION'}], 60)
        self.evloop.flush()
        # call parent
        RunningIdentifiersTest.tearDown(self)

    def test_continue(self):
        """ Test the CONTINUE running failure strategy. """
        print('\n### Testing CONTINUE running failure strategy')
        # force the movie_server_01 to exit with a fake segmentation fault
        self.local_supervisor.signalProcess('database:movie_server_01', 'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        assert {'name': 'movie_server_01', 'expected': False, 'state': 100}.items() < event.items()
        # application should be still running with 2 other movie servers, but with minor failure
        event = self._get_next_application_status()
        subset = {'application_name': 'database', 'major_failure': False, 'minor_failure': True,
                  'statename': 'RUNNING'}
        assert subset.items() < event.items()
        # no further event expected
        with self.assertRaises(Empty):
            self.evloop.event_queue.get(True, 5)
        with self.assertRaises(Empty):
            self.evloop.application_queue.get(True, 2)

    def test_restart_process(self):
        """ Test the RESTART_PROCESS running failure strategy. """
        print('\n### Testing RESTART_PROCESS running failure strategy')
        # call for restart on the node where web_browser is running
        proxy = self.proxies[self.web_browser_node_name]
        proxy.supervisor.restart()
        # STARTING / RUNNING events are expected for web_browser from a new node
        # STARTING / RUNNING events may be received for disk_handler from the restarted node
        # as a node is being restarted, lots of events may be expected (new DEPLOYMENT)
        # focus only on web_browser
        expected_events = [{'group': 'web_movies', 'name': 'web_browser', 'state': 10},
                           {'group': 'web_movies', 'name': 'web_browser', 'state': 20}]
        received_events = self.evloop.wait_until_events(self.evloop.event_queue, expected_events, 25)
        self.assertEqual(2, len(received_events))
        self.assertEqual([], expected_events)
        # STARTING / RUNNING events are expected for web_movies application
        # nothing for disk_handler as it is unmanaged
        expected_events = [{'application_name': 'web_movies', 'major_failure': False, 'minor_failure': False,
                            'statename': 'STARTING'},
                           {'application_name': 'web_movies', 'major_failure': False, 'minor_failure': False,
                            'statename': 'RUNNING'}]
        received_events = self.evloop.wait_until_events(self.evloop.application_queue, expected_events, 2)
        self.assertEqual(2, len(received_events))
        self.assertEqual([], expected_events)
        # with for Supvisors to reach the OPERATION state before leaving
        self.evloop.wait_until_events(self.evloop.supvisors_queue, [{'statename': 'OPERATION'}], 60)

    def test_stop_application(self):
        """ Test the STOP_APPLICATION running failure strategy. """
        print('\n### Testing STOP_APPLICATION running failure strategy')
        # get the hmi running location
        infos = self.local_supvisors.get_process_info('my_movies:hmi')
        hmi_info = infos[0]
        self.assertEqual('RUNNING', hmi_info['statename'])
        self.assertEqual(1, len(hmi_info['identifiers']))
        hmi_node = hmi_info['identifiers'][0]
        # force the hmi to exit with a fake segmentation fault
        hmi_proxy = self.proxies[hmi_node].supervisor
        hmi_proxy.signalProcess('my_movies:hmi', 'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        assert {'name': 'hmi', 'expected': False, 'state': 100}.items() < event.items()
        # application should be still running with manager, but with major failure due to web_server
        # that cannot be started, and with minor failure due to hmi crash
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': True,
                  'statename': 'RUNNING'}
        assert subset.items() < event.items()
        # STOPPING / STOPPED events are expected for the manager
        event = self._get_next_process_event()
        assert {'name': 'manager', 'state': 40}.items() < event.items()
        # application should be stopping
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': True,
                  'statename': 'STOPPING'}
        assert subset.items() < event.items()
        event = self._get_next_process_event()
        assert {'name': 'manager', 'state': 0}.items() < event.items()
        # application should be stopped
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': True,
                  'statename': 'STOPPED'}
        assert subset.items() < event.items()
        # no further event expected
        with self.assertRaises(Empty):
            self.evloop.event_queue.get(True, 5)
        with self.assertRaises(Empty):
            self.evloop.application_queue.get(True, 2)

    def test_restart_application(self):
        """ Test the RESTART_APPLICATION running failure strategy. """
        print('\n### Testing RESTART_APPLICATION running failure strategy')
        # get the manager running location
        infos = self.local_supvisors.get_process_info('my_movies:manager')
        manager_info = infos[0]
        self.assertEqual('RUNNING', manager_info['statename'])
        self.assertEqual(1, len(manager_info['identifiers']))
        manager_node = manager_info['identifiers'][0]
        # force the manager to exit with a fake segmentation fault
        manager_proxy = self.proxies[manager_node].supervisor
        manager_proxy.signalProcess('my_movies:manager', 'SEGV')
        # an EXIT event is expected for this process
        event = self._get_next_process_event()
        assert {'name': 'manager', 'expected': False, 'state': 100}.items() < event.items()
        # application should be still running with hmi but with major failure
        # because of required manager and web_server that are not running
        # WARN: if minor_failure is detected True, check if check_starting_strategy has been run before
        # converter_09 may be FATAL, leading to minor failure
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'RUNNING'}
        assert subset.items() < event.items()
        # STOPPING / STOPPED events are expected for the hmi
        event = self._get_next_process_event()
        assert {'name': 'hmi', 'state': 40}.items() < event.items()
        # application should be stopping
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'STOPPING'}
        assert subset.items() < event.items()
        event = self._get_next_process_event()
        assert {'name': 'hmi', 'state': 0}.items() < event.items()
        # application should be stopped
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'STOPPED'}
        assert subset.items() < event.items()
        # STARTING / RUNNING events are expected for the manager
        event = self._get_next_process_event()
        assert {'name': 'manager', 'state': 10}.items() < event.items()
        # application should be starting, with major failure because of required web_server that is not started yet
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'STARTING'}
        assert subset.items() < event.items()
        event = self._get_next_process_event()
        assert {'name': 'manager', 'state': 20}.items() < event.items()
        # application should be running, with major failure because of required web_server that is not started yet
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'RUNNING'}
        assert subset.items() < event.items()
        # FATAL event is expected for the web_server
        event = self._get_next_process_event()
        assert {'name': 'web_server', 'state': 200}.items() < event.items()
        # application should be still running, with major failure because of web_server that cannot be started
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'RUNNING'}
        assert subset.items() < event.items()
        # STARTING / RUNNING events are expected for the hmi
        event = self._get_next_process_event()
        assert {'name': 'hmi', 'state': 10}.items() < event.items()
        # application should be starting, with major failure because of web_server that cannot be started
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'STARTING'}
        assert subset.items() < event.items()
        event = self._get_next_process_event()
        assert {'name': 'hmi', 'state': 20}.items() < event.items()
        # application should be running, with major failure because of web_server that cannot be started
        event = self._get_next_application_status()
        subset = {'application_name': 'my_movies', 'major_failure': True, 'minor_failure': False,
                  'statename': 'RUNNING'}
        assert subset.items() < event.items()
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
    parser = argparse.ArgumentParser(description='Check the Supvisors running failure strategies.')
    parser.add_argument('-p', '--port', type=int, default=60002, help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
