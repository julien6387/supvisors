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

import argparse
import sys

from .sequence_checker import *


class CheckStartSequenceTest(CheckSequenceTest):
    """ Test case to check the sequencing of the starting test application. """

    def test_sequencing(self):
        """ Test the whole sequencing of the starting of the test application.
        At this point, Supvisors is in DEPLOYMENT phase.
        This process is the first to be started. """
        # wait for address_queue to trigger
        self.get_nodes()
        # test the last events received for this process
        self.check_self_starting()
        # test the starting of applications
        self.check_import_database_starting()
        self.check_database_starting()
        self.check_my_movies_starting()
        self.check_player_starting()
        self.check_web_movies_starting()
        # final test (import database expected to be stopped)
        self.assertFalse(self.context.has_events())

    def check_self_starting(self):
        """ Test the events received that corresponds to the starting of this process. """
        # define 'test' application
        application = Application('test')
        self.context.add_application(application)
        program = Program('check_start_sequence')
        # this process 'test:check_start_sequence' is already starting
        program.state = ProcessStates.STARTING
        application.add_program(program)
        # define the expected events for this process
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, self.HOST_01))
        # test the events received are compliant
        self.check_events()
        self.assertFalse(self.context.has_events())

    def check_import_database_starting(self):
        """ Check the starting of the import_database application.
        The mount_disk process is started first, then the copy_error (failure expected).
        The application is configured to be stopped because of the failure. """
        # define 'import_database' application
        application = Application('import_database')
        self.context.add_application(application)
        for program_name in ['mount_disk_00', 'mount_disk_01']:
            application.add_program(Program(program_name, True))
        application.add_program(Program('copy_error', True))
        # check events
        self.check_mount_disk_starting()
        self.check_copy_error_starting()
        self.check_mount_disk_stopping()

    def check_mount_disk_starting(self):
        """ Check the starting of the mount_disk program. """
        config = [('mount_disk_00', self.HOST_02),
                  ('mount_disk_01', self.HOST_03)]
        # define the expected events for the mount_disk program
        application = self.context.get_application('import_database')
        for program_name, node_name in config:
            program = application.get_program(program_name)
            if node_name in self.nodes:
                program.add_event(ProcessStateEvent(ProcessStates.STARTING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.RUNNING, node_name))
            else:
                program.add_event(ProcessStateEvent(ProcessStates.FATAL, node_name))
        # check that the events received correspond to the expected
        self.check_events('import_database')
        self.assertFalse(self.context.has_events('import_database'))

    def check_copy_error_starting(self):
        """ Check the starting of the copy_error program. """
        # define the expected events for the copy_error program
        if all(node_name in self.nodes for node_name in [self.HOST_02, self.HOST_03]):
            program = self.context.get_program('import_database:copy_error')
            program.add_event(ProcessStateEvent(ProcessStates.STARTING, self.HOST_01))
            program.add_event(ProcessStateEvent(ProcessStates.BACKOFF, self.HOST_01))
            program.add_event(ProcessStateEvent(ProcessStates.FATAL))
            # test the events received are compliant
            self.check_events()
            self.assertFalse(self.context.has_events())

    def check_mount_disk_stopping(self):
        """ Program the stopping of the program.state program. """
        config = [('mount_disk_00', self.HOST_02),
                  ('mount_disk_01', self.HOST_03)]
        # define the expected events for the mount_disk program
        application = self.context.get_application('import_database')
        for program_name, node_name in config:
            if node_name in self.nodes:
                program = application.get_program(program_name)
                program.add_event(ProcessStateEvent(ProcessStates.STOPPING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.STOPPED, node_name))
        # do NOT check the events received at this stage
        # stopping events will be mixed with the starting events of the following applications

    def check_database_starting(self):
        """ Check the starting of the database application.
        The movie_server_xx processes are started first, then the register_movies_xx.
        FATAL process events are expected, according to the test platform. """
        # define 'import_database' application
        application = Application('database')
        self.context.add_application(application)
        for program_name in ['movie_server_01', 'movie_server_02', 'movie_server_03']:
            application.add_program(Program(program_name))
        for program_name in ['register_movies_01', 'register_movies_02', 'register_movies_03']:
            application.add_program(Program(program_name, False, True))
        # check events
        self.check_movie_server_starting()
        self.check_register_movies_starting()

    def check_movie_server_starting(self):
        """ Check the starting of the movie_server programs. """
        config = [('movie_server_01', self.HOST_01),
                  ('movie_server_02', self.HOST_02),
                  ('movie_server_03', self.HOST_03)]
        # define the expected events for the movie_server_xx programs
        application = self.context.get_application('database')
        for program_name, node_name in config:
            program = application.get_program(program_name)
            if node_name in self.nodes:
                program.add_event(ProcessStateEvent(ProcessStates.STARTING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.RUNNING, node_name))
            else:
                program.add_event(ProcessStateEvent(ProcessStates.FATAL))
        # check that the events received are compliant
        self.check_events('database')
        self.assertFalse(self.context.has_events('database'))

    def check_register_movies_starting(self):
        """ Check the starting of the register_movies programs. """
        config = [('register_movies_01', self.HOST_01),
                  ('register_movies_02', self.HOST_03)]
        # define the expected events for the register_movies_xx programs
        application = self.context.get_application('database')
        for program_name, node_name in config:
            program = application.get_program(program_name)
            if node_name in self.nodes:
                program.add_event(ProcessStateEvent(ProcessStates.STARTING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.RUNNING, node_name))
                program.add_event(ProcessStateEvent(ProcessStates.EXITED))
            else:
                program.add_event(ProcessStateEvent(ProcessStates.FATAL))
        # check that the events received are compliant
        self.check_events('database')
        self.assertFalse(self.context.has_events('database'))

    def check_my_movies_starting(self):
        """ Check the starting of the my_movies application.
        The manager process is started first, then the web_server, finally the hmi.
        In the my_movies application, there should be a major_failure due to the web_server
        that is configured not to start. """
        # define 'my_movies' application
        application = Application('my_movies')
        self.context.add_application(application)
        application.add_program(Program('manager', True))
        application.add_program(Program('web_server', True))
        application.add_program(Program('hmi'))
        # check events
        self.check_manager_starting()
        self.check_web_server_starting()
        self.check_hmi_starting()

    def check_manager_starting(self):
        """ Check the starting of the manager program. """
        # define the expected events for the manager program
        program = self.context.get_program('my_movies:manager')
        program.add_event(ProcessStateEvent(ProcessStates.STARTING, self.HOST_01))
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, self.HOST_01))
        # check that the events received are compliant
        self.check_events('my_movies')
        self.assertFalse(self.context.has_events('my_movies'))

    def check_web_server_starting(self):
        """ Check the starting of the web_server program. """
        # define the expected events for the web_server program
        program = self.context.get_program('my_movies:web_server')
        program.add_event(ProcessStateEvent(ProcessStates.FATAL))
        # check that the events received are compliant
        self.check_events('my_movies')
        self.assertFalse(self.context.has_events('my_movies'))

    def check_hmi_starting(self):
        """ Check the starting of the hmi program. """
        # define the expected events for the hmi program
        program = self.context.get_program('my_movies:hmi')
        node_name = self.HOST_02 if self.HOST_02 in self.nodes else self.HOST_01
        program.add_event(ProcessStateEvent(ProcessStates.STARTING, node_name))
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, node_name))
        # check that the events received are compliant
        self.check_events('my_movies')
        self.assertFalse(self.context.has_events('my_movies'))

    def check_player_starting(self):
        """ Check the starting of the player application.
        The test_reader process is started first (wrong exit code expected).
        The starting of the application is configured to be aborted
        after the failure. """
        # define 'player' application
        application = Application('player')
        self.context.add_application(application)
        application.add_program(Program('test_reader', True, True))
        application.add_program(Program('movie_player'))
        # check events
        self.check_test_reader_starting()

    def check_test_reader_starting(self):
        """ Check the starting of the test_reader program. """
        # define the expected events for the test_reader program
        program = self.context.get_program('player:test_reader')
        node_name = self.HOST_03 if self.HOST_03 in self.nodes else self.HOST_01
        program.add_event(ProcessStateEvent(ProcessStates.STARTING, node_name))
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, node_name))
        program.add_event(ProcessStateEvent(ProcessStates.EXITED, node_name))
        # check that the events received are compliant
        self.check_events('player')
        self.assertFalse(self.context.has_events('player'))

    def check_web_movies_starting(self):
        """ Check the starting of the web_movies application.
        It contains only the web_browser program. """
        # define 'my_movies' application
        application = Application('web_movies')
        self.context.add_application(application)
        program = Program('web_browser')
        application.add_program(program)
        # define the expected events for the web_browser program
        # WARN: if errors happen, like "AssertionError: 'RUNNING' != 'BACKOFF'"
        #  this is probably because there is an instance of firefox already running before supervisord has been started
        #  close it before the test
        address = self.HOST_02 if self.HOST_02 in self.nodes else self.HOST_01
        program.add_event(ProcessStateEvent(ProcessStates.STARTING, address))
        program.add_event(ProcessStateEvent(ProcessStates.RUNNING, address))
        # check that the events received are compliant
        self.check_events('web_movies')
        self.assertFalse(self.context.has_events('web_movies'))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    # get arguments
    parser = argparse.ArgumentParser(description='Check the starting sequence using Supvisors events.')
    parser.add_argument('-p', '--port', type=int, default=60002,
                        help="the event port of Supvisors")
    args = parser.parse_args()
    SupvisorsEventQueues.PORT = args.port
    # start unittest
    unittest.main(defaultTest='test_suite')
