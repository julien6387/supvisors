#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from supervisor.states import *
from supervisor.childutils import getRPCInterface

from .event_queues import SupvisorsEventQueues
from .sequence_checker import *


class CheckStopSequenceTest(CheckSequenceTest):
    """ Test case to check the sequencing of the stopping test application. """

    def test_sequencing(self):
        """ Test the whole sequencing of the starting of the test application.
        At this point, Supvisors is in OPERATION phase.
        This process is the first to be started. """
        # store a proxy to perform XML-RPC requests
        self.proxy = getRPCInterface(os.environ)
        # wait for address_queue to trigger
        self.get_nodes()
        # define the context to know which process is running
        self.create_context()
        # start a converter to sync
        self.proxy.supvisors.start_args('my_movies:converter_05')
        # empty queues (pull STARTING / RUNNING events)
        self.check_converter_running()
        # send restart request
        self.proxy.supvisors.restart()
        # test the stopping of service application
        self.check_service_stopping()
        # test the stopping of web_movies application
        self.check_web_movies_stopping()
        # test the stopping of my_movies application
        self.check_my_movies_stopping()
        # test the stopping of database application
        self.check_database_stopping()
        # cannot test the last events received for this process

    def create_context(self):
        """ Store info and rules about the running processes of the application considered. """
        # get info about all processes
        info_list = self.proxy.supvisors.get_all_process_info()
        # define applications and programs
        for info in info_list:
            # required is set later. wait_exit is not used here
            program = Program(info['process_name'])
            program.state = info['statecode']
            program.node_names = set(info['addresses'])
            application = self.context.get_application(info['application_name'])
            if not application:
                # create application if not found
                application = Application(info['application_name'])
                self.context.add_application(application)
            application.add_program(program)
        # set required status
        self.context.get_program('my_movies:manager').required = True
        self.context.get_program('my_movies:web_server').required = True

    def check_converter_running(self):
        """ Check the start sequence of the converter program. """
        # define the expected events for this process
        program = self.context.get_program('my_movies:converter_05')
        program.add_event(ProcessStateEvent(ProcessStates.STARTING, self.HOST_01))
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, self.HOST_01))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())

    def check_service_stopping(self):
        """ Check the stopping sequence of the service application.
        This one is complex to test as there may ne multiple instances running for the same program. """
        program = self.context.get_program('service:disk_handler')
        if program.state in RUNNING_STATES:
            node_names = program.node_names.copy()
            # event sequence on nodes is quite unpredictible so test only process states
            while len(node_names) > 1:
                # STOPPING then STOPPED on one node in list. still RUNNING on others
                program.add_event(ProcessStateEvent(ProcessStates.RUNNING))
                program.add_event(ProcessStateEvent(ProcessStates.RUNNING))
                node_names.pop()
            # STOPPING then STOPPED on last node
            program.add_event(ProcessStateEvent(ProcessStates.STOPPING))
            program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())

    def check_web_movies_stopping(self):
        """ Check the stopping sequence of the web_movies application. """
        program = self.context.get_program('web_movies:web_browser')
        if program.state in RUNNING_STATES:
            for node_name in program.node_names:
                program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())

    def check_my_movies_stopping(self):
        """ Check the stopping sequence of the my_movies application. """
        # get my_movies application
        application = self.context.get_application('my_movies')
        # check processes in stop_sequence 0
        for program in application.programs.values():
            if program.program_name not in ['hmi', 'manager'] and program.state in RUNNING_STATES:
                for node_name in program.node_names:
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())
        # check processes in stop_sequence 1
        program = application.get_program('hmi')
        if program.state in RUNNING_STATES:
            for node_name in program.node_names:
                program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())
        # check processes in stop_sequence 2
        program = application.get_program('manager')
        if program.state in RUNNING_STATES:
            for node_name in program.node_names:
                program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())

    def check_database_stopping(self):
        """ Check the stopping sequence of the database application. """
        # get database application
        application = self.context.get_application('database')
        # check movie_server_processes
        for program in application.programs.values():
            if program.program_name in ['movie_server_01', 'movie_server_02', 'movie_server_03'] \
                    and program.state in RUNNING_STATES:
                for node_name in program.node_names:
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    # catch supervisor termination signal
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # get arguments
    import argparse
    parser = argparse.ArgumentParser(description='Check the stopping sequence using Supvisors events.')
    parser.add_argument('-p', '--port', type=int, default=60002,
                        help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
