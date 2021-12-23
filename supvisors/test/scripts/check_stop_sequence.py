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

import signal
import sys

from .sequence_checker import *


class CheckStopSequenceTest(CheckSequenceTest):
    """ Test case to check the sequencing of the stopping test application. """

    def test_sequencing(self):
        """ Test the whole sequencing of the starting of the test application.
        At this point, Supvisors is in OPERATION phase.
        This process is the first to be started. """
        # store a proxy to perform XML-RPC requests
        self.proxy = getRPCInterface(os.environ)
        # wait for node_queue to trigger
        self.get_nodes()
        # define the context to know which process is running
        self.create_context()
        # start a converter to sync
        self.proxy.supvisors.start_args('my_movies:converter_05')
        # empty queues (pull STARTING / RUNNING events)
        self.check_converter_running()
        # send restart request
        self.proxy.supvisors.restart()
        # test the stopping of my_movies application
        self.check_my_movies_stopping()
        # test the stopping of database application
        self.check_database_stopping()
        # test the stopping of web_movies application
        self.check_web_movies_stopping()
        # test the stopping of service application
        self.check_unmanaged_stopping()
        # cannot test the last event received for this process

    def create_context(self):
        """ Store info and rules about the running processes of the application considered. """
        # get info about all processes
        info_list = self.proxy.supvisors.get_all_process_info()
        # define applications and programs
        for info in info_list:
            # required is set later. wait_exit is not used here
            program = Program(info['process_name'])
            program.state = info['statecode']
            program.node_names = set(info['nodes'])
            application = self.context.get_application(info['application_name'])
            if not application:
                # create application if not found
                application = Application(info['application_name'])
                self.context.add_application(application)
            application.add_program(program)
        # set required status
        self.context.get_program('my_movies:manager').required = True
        self.context.get_program('my_movies:web_server').required = True
        # set managed status
        self.context.get_application('service').managed = False
        disk_handler = self.context.get_application('disk_handler')
        if disk_handler:
            # only on cliche83
            disk_handler.managed = False
        self.context.get_application('evt_listener').managed = False

    def check_converter_running(self):
        """ Check the start sequence of the converter program. """
        # define the expected events for this process
        program = self.context.get_program('my_movies:converter_05')
        program.add_event(ProcessStateEvent(ProcessStates.STARTING, self.HOST_01))
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, self.HOST_01))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())

    def check_unmanaged_stopping(self):
        """ Check the stopping sequence of the unmanaged applications.
        This one is complex to test as there may be multiple instances running for the same program.
        And this is mixed with the stopping of disk_handler group. """
        # configure service application stop sequence
        program = self.context.get_program('service:disk_handler')
        if program.state in RUNNING_STATES:
            # 2 instances max on cliche81 and cliche82
            # 2 possible sequences, depending on when the first event of the second node arrives before or
            # after the second event of the first node:
            #    * RUNNING RUNNING STOPPING STOPPED
            #    * RUNNING STOPPING STOPPING STOPPED
            if len(program.node_names) > 1:
                program.add_event(ProcessStateEvent(ProcessStates.RUNNING))
                program.add_event(ProcessStateEvent([ProcessStates.RUNNING, ProcessStates.STOPPING]))
            program.add_event(ProcessStateEvent(ProcessStates.STOPPING))
            program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # configure disk_handler stop sequence
        program = self.context.get_program('disk_handler')
        if program:
            if program.state in RUNNING_STATES:
                for node_name in program.node_names:
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # configure evtlistener stop sequence
        program = self.context.get_program('evt_listener:evt_listener_00')
        if program:
            if program.state in RUNNING_STATES:
                for node_name in program.node_names:
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPED))
        # configure self stop sequence: only the STOPPING event will be received
        program = self.context.get_program('test:check_stop_sequence')
        if program:
            if program.state in RUNNING_STATES:
                for node_name in program.node_names:
                    program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
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
        # check processes in stop_sequence 3
        program = application.get_program('manager')
        if program.state in RUNNING_STATES:
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
        # check processes in stop_sequence 0
        for program in application.programs.values():
            if program.program_name not in ['hmi', 'manager'] and program.state in RUNNING_STATES:
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
    # catch and ignore supervisor termination signal
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
