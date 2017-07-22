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
from Queue import Empty

from supervisor.childutils import getRPCInterface
from supervisor.options import split_namespec
from supervisor.states import (RUNNING_STATES, STOPPED_STATES)
from supvisors.client.subscriber import create_logger
from supvisors.ttypes import ApplicationStates, ProcessStates

from scripts.event_queue import SupvisorsEventQueues


class ProcessStateEvent(object):
    """ Definition of an expected event coming from a defined address. """

    def __init__(self, statecode, address=None):
        """ Initialization of the attributes. """
        self.statecode = statecode
        self.address = address

    @property
    def statename(self):
        return ProcessStates._to_string(self.statecode)

    def get_state(self):
        """ Return the state in a Supvisors / Supervisor format. """
        return {'statename': self.statename, 'statecode': self.statecode}


class Program(object):
    """ Simple definition of a program. """

    def __init__(self, program_name, required=False, wait_exit=False):
        """ Initialization of the attributes. """
        self.program_name = program_name
        self.state = ProcessStates.UNKNOWN
        self.address = None
        self.expected_exit = True
        self.required = required
        self.wait_exit = wait_exit
        self.state_events = []

    def add_event(self, event):
        """ Add an event to the list of expected events. """
        self.state_events.append(event)

    def pop_event(self):
        """ Pop an event from the list of expected events. """
        return self.state_events.pop(0)


class Application:
    """ Simple definition of an application. """

    def __init__(self, application_name):
        """ Initialization of the attributes. """
        self.application_name = application_name
        # create dict of states / process_names
        self.major_failure, self.minor_failure = (False, ) * 2
        # event dictionary
        self.programs = {}

    def add_program(self, program):
        """ Add a program to the list. """
        self.programs[program.program_name] = program

    def get_program(self, program_name):
        """ Get a program from the list using its name. """
        return self.programs.get(program_name, None)

    def is_starting(self):
        """ Return True if the application has a starting program. """
        for program in self.programs.values():
            if program.state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                return True
        return False

    def is_stopping(self):
        """ Return True if the application has a stopping program and no starting program. """
        stopping = False
        for program in self.programs.values():
            if program.state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                return False
            if program.state == ProcessStates.STOPPING:
                stopping = True
        return stopping

    def is_running(self):
        """ Return True if the application has a running program and no starting or stopping program. """
        running = False
        for program in self.programs.values():
            if program.state in [ProcessStates.STARTING, ProcessStates.BACKOFF, ProcessStates.STOPPING]:
                return False
            if program.state == ProcessStates.RUNNING:
                running = True
        return running

    def is_stopped(self):
        """ Return True if the application has only stopped programs. """
        for program in self.programs.values():
            if program.state in [ProcessStates.STOPPING] + list(RUNNING_STATES):
                return False
        return True

    def has_major_failure(self):
        """ Return True if there is a stopped required program in a running application. """
        major = False
        for program in self.programs.values():
            if program.state in STOPPED_STATES and program.required:
                major = True
        return major and (self.is_running() or self.is_starting())

    def has_minor_failure(self):
        """ Return True if there is a fatal optional program in a running application. """
        minor = False
        for program in self.programs.values():
            if not program.required and (program.state == ProcessStates.FATAL or
                    (program.state == ProcessStates.EXITED and not program.expected_exit)):
                minor = True
        return minor and (self.is_running() or self.is_starting())


class Context:
    """ Simple definition of a list of applications. """

    def __init__(self):
        """ Initialization of the attributes. """
        self.applications = {}

    def add_application(self, application):
        """ Add an application to the context. """
        self.applications[application.application_name] = application

    def get_application(self, application_name):
        """ Get an application from the context using its name. """
        return self.applications.get(application_name, None)

    def get_program(self, namespec):
        """ Get a program from the context using its namespec. """
        application_name, process_name = split_namespec(namespec)
        return self.get_application(application_name).get_program(process_name)

    def has_events(self, application_name=None):
        """ Return True if the programs of the application contain events not received yet. """
        application_list = [self.get_application(application_name)] if application_name else self.applications.values()
        for application in application_list:
            for program in application.programs.values():
                if program.state_events:
                    return True
        return False


class CheckSequenceTest(unittest.TestCase):
    """ Common class used to check starting and stopping sequences. """

    PORT = 60002

    def setUp(self):
        """ The setUp starts the subscriber to the Supvisors events and get the event queues. """
        # create logger using a BoundIO
        self.logger = create_logger(logfile=None)
        # get the addresses
        addresses_info = getRPCInterface(os.environ).supvisors.get_all_addresses_info()
        print addresses_info
        self.HOST_01 = addresses_info[0]['address_name']
        self.HOST_02 = addresses_info[1]['address_name']
        self.HOST_03 = addresses_info[2]['address_name']
        self.logger.info('working with HOST_01={} HOST_02={} HOST_03={}'.format(self.HOST_01, self.HOST_02, self.HOST_03))
        # create a context
        self.context = Context()
        # create the thread of event subscriber
        self.event_loop = SupvisorsEventQueues(self.PORT, self.logger)
        # get the queues
        self.address_queue = self.event_loop.event_queues[1]
        self.application_queue = self.event_loop.event_queues[2]
        self.process_queue = self.event_loop.event_queues[3]
        # start the thread
        self.event_loop.start()

    def tearDown(self):
        """ The tearDown stops the subscriber to the Supvisors events. """
        self.event_loop.stop()
        self.event_loop.join()

    def get_addresses(self):
        """ Wait for address_queue to put the list of active addresses. """
        try:
            self.addresses = self.address_queue.get(True, 30)
            self.assertGreater(len(self.addresses), 0)
        except Empty:
            self.fail('failed to get the address event in the last 30 seconds')

    def check_events(self, application_name=None):
        """ Receive and check events for processes and applications. """
        while self.context.has_events(application_name):
            # wait for a process event
            try:
                data = self.process_queue.get(True, 30)
            except Empty:
                self.fail('failed to get the expected events for this process')
            self.check_process_event(data)
            # wait for an application event
            try:
                data = self.application_queue.get(True, 2)
            except Empty:
                self.fail('failed to get the expected events for this process')
            self.check_application_event(data)

    def check_process_event(self, event):
        """ Check if the received process event corresponds to expectation. """
        self.logger.info('Checking process event: {}'.format(event))
        # check that event corresponds to an expected application
        application_name = event['application_name']
        application = self.context.get_application(application_name)
        self.assertIsNotNone(application)
        # check that event corresponds to an expected process
        process_name = event['process_name'] 
        self.assertIn(process_name, application.programs.keys())
        program = application.get_program(process_name)
        self.assertIsNotNone(program)
       # pop next event and clean if necessary
        state_event = program.pop_event()
        self.assertIsNotNone(state_event)
        # check the process' state
        self.assertEqual(state_event.statename, event['statename'])
        self.assertEqual(state_event.statecode, event['statecode'])
        # check the running address
        if state_event.statecode in [ProcessStates.STOPPING] + list(RUNNING_STATES):
            self.assertListEqual([state_event.address], event['addresses'])
            program.address = state_event.address
        # update program state
        program.state = state_event.statecode
        program.expected_exit = event['expected_exit']

    def check_application_event(self, event):
        """ Check if the received application event corresponds to expectation. """
        self.logger.info('Checking application event: {}'.format(event))
        # check that event corresponds to an expected application
        application_name = event['application_name']
        application = self.context.get_application(application_name)
        self.assertIsNotNone(application)
        # check event contents in accordance with context
        if application.is_starting():
            self.assertDictContainsSubset({'statename': 'STARTING', 'statecode': ApplicationStates.STARTING}, event)
        elif application.is_stopping():
            self.assertDictContainsSubset({'statename': 'STOPPING', 'statecode': ApplicationStates.STOPPING}, event)
        elif application.is_running():
            self.assertDictContainsSubset({'statename': 'RUNNING', 'statecode': ApplicationStates.RUNNING}, event)
        else:
            self.assertDictContainsSubset({'statename': 'STOPPED', 'statecode': ApplicationStates.STOPPED}, event)
        self.assertEqual(application.has_major_failure(), event['major_failure'])
        self.assertEqual(application.has_minor_failure(), event['minor_failure'])
