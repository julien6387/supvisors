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

import unittest
from queue import Empty
from typing import Dict

import zmq.asyncio
from supervisor.options import split_namespec
from supervisor.states import ProcessStates, getProcessStateDescription, RUNNING_STATES, STOPPED_STATES

from supvisors.client.clientutils import create_logger
from supvisors.ttypes import ApplicationStates
from .event_queues import SupvisorsEventQueues


class ProcessStateEvent:
    """ Definition of an expected event coming from a defined Supvisors instance. """

    def __init__(self, statecode, identifiers=None):
        """ Initialization of the attributes. """
        self.statecode = statecode
        self.identifiers = []
        if type(identifiers) is str:
            self.identifiers = [identifiers]
        elif type(identifiers) is list:
            self.identifiers = identifiers

    @property
    def statename(self):
        if type(self.statecode) is list:
            return [getProcessStateDescription(statecode) for statecode in self.statecode]
        return getProcessStateDescription(self.statecode)

    def get_state(self):
        """ Return the state in a Supvisors / Supervisor format. """
        return {'statename': self.statename, 'statecode': self.statecode}

    def __str__(self):
        """ Printable version. """
        return 'statename={} statecode={}'.format(self.statename, self.statecode)


class Program:
    """ Simple definition of a program. """

    def __init__(self, program_name, required=False, wait_exit=False):
        """ Initialization of the attributes. """
        self.program_name = program_name
        self.state = ProcessStates.UNKNOWN
        self.identifiers = set()
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

    def __str__(self):
        """ Return a printable form. """
        return f'Program(program_name={self.program_name} state={self.state} identifiers={self.identifiers})'


def database_status_logic(app):
    """ Specific major failure for database application. """
    for proc_name in ['register_movies_01', 'register_movies_02', 'register_movies_03']:
        process = app.programs[proc_name]
        if not ((process.state in RUNNING_STATES)
                or (process.state == ProcessStates.EXITED and process.expected_exit)):
            return True
    any_movie_server = False
    for proc_name in ['movie_server_01', 'movie_server_02', 'movie_server_03']:
        process = app.programs[proc_name]
        if (process.state in RUNNING_STATES
                or (process.state == ProcessStates.EXITED and process.expected_exit)):
            any_movie_server = True
    return not any_movie_server


class Application:
    """ Simple definition of an application. """

    def __init__(self, application_name, status_logic=None):
        """ Initialization of the attributes. """
        self.application_name = application_name
        # failure handling
        self.status_logic = status_logic
        # event dictionary
        self.programs = {}

    def __str__(self):
        """ Return a printable form. """
        return (f'Application(application_name={self.application_name}'
                f' programs={[str(prg) for prg in self.programs.values()]})')

    def add_program(self, program):
        """ Add a program to the list. """
        self.programs[program.program_name] = program

    def get_program(self, program_name):
        """ Get a program from the list using its name. """
        return self.programs.get(program_name, None)

    def is_starting(self):
        """ Return True if the application has a starting program. """
        for program in self.programs.values():
            if program.state in (ProcessStates.STARTING, ProcessStates.BACKOFF):
                return True
        return False

    def is_stopping(self):
        """ Return True if the application has a stopping program and no starting program. """
        stopping = False
        for program in self.programs.values():
            if program.state in (ProcessStates.STARTING, ProcessStates.BACKOFF):
                return False
            if program.state == ProcessStates.STOPPING:
                stopping = True
        return stopping

    def is_running(self):
        """ Return True if the application has a running program and no starting or stopping program. """
        running = False
        for program in self.programs.values():
            if program.state in (ProcessStates.STARTING,
                                 ProcessStates.BACKOFF,
                                 ProcessStates.STOPPING):
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
        for program in self.programs.values():
            if program.state in STOPPED_STATES and program.required:
                return True
        return False

    def has_minor_failure(self):
        """ Return True if there is a fatal optional program in a running application. """
        for program in self.programs.values():
            if not program.required and (program.state == ProcessStates.FATAL or
                                         (program.state == ProcessStates.EXITED and
                                          not program.expected_exit)):
                return True
        return False

    def get_failures(self):
        # formula case
        if self.status_logic:
            major_failure = self.status_logic(self)
            minor_failure = False
            if not major_failure:
                for program in self.programs.values():
                    if (program.state == ProcessStates.FATAL or
                            (program.state == ProcessStates.EXITED and not program.expected_exit)):
                        minor_failure = True
            return major_failure, minor_failure
        # required case
        return self.has_major_failure(), self.has_minor_failure()


class Context:
    """ Simple definition of a list of applications. """

    def __init__(self):
        """ Initialization of the attributes. """
        self.applications: Dict[str, Application] = {}

    def add_application(self, application: Application) -> None:
        """ Add an application to the context. """
        self.applications[application.application_name] = application

    def get_application(self, application_name: str) -> Application:
        """ Get an application from the context using its name. """
        return self.applications.get(application_name, None)

    def get_program(self, namespec: str):
        """ Get a program from the context using its namespec. """
        application_name, process_name = split_namespec(namespec)
        application = self.get_application(application_name)
        if application:
            return application.get_program(process_name)

    def has_events(self, application_name: str = None) -> bool:
        """ Return True if the programs of the application contain events not received yet. """
        application_list = [self.get_application(application_name)] if application_name else self.applications.values()
        for application in application_list:
            for program in application.programs.values():
                if program.state_events:
                    # for debug
                    # print('### {} - {}'.format(program.program_name, [str(evt) for evt in program.state_events]))
                    return True


class SequenceChecker(SupvisorsEventQueues):
    """ The SequenceChecker is a python thread that connects to Supvisors
    and stores the application and process events received into queues. """

    def __init__(self, zcontext, logger):
        """ Initialization of the attributes.
        Test relies on 4 instances so theoretically, only 4 notifications are needed to know the running instances.
        The asynchronism forces working on 4*2-1 notifications.
        The startsecs of the ini file of this program is then set to 40 seconds.
        """
        SupvisorsEventQueues.__init__(self, zcontext, logger)
        # create a set of instances
        self.identifiers = set()
        # create queues to store messages
        self.nb_identifiers_notifications = 0

    def configure(self):
        """ Subscribe to Supvisors instances status only. """
        self.subscribe_instance_status()

    def on_instance_status(self, data):
        """ Pushes the Supvisors Instance Status message into a queue. """
        self.logger.info(f'got Supvisors Instance Status message: {data}')
        if data['statename'] == 'RUNNING':
            self.identifiers.add(data['identifier'])
        # check the number of notifications
        self.nb_identifiers_notifications += 1
        if self.nb_identifiers_notifications == 7:
            self.logger.info(f'instances: {self.identifiers}')
            # got all notification, unsubscribe from SupvisorsInstanceStatus
            self.unsubscribe_instance_status()
            # subscribe to application and process status
            self.subscribe_application_status()
            self.subscribe_process_status()
            # notify CheckSequence with an event in start_queue
            self.instance_queue.put(self.identifiers)


class CheckSequenceTest(unittest.TestCase):
    """ Common class used to check starting and stopping sequences. """

    HOST_01 = '17.0.1.11:60000'
    HOST_02 = 'supv02:60000'
    HOST_03 = '192.168.1.70:30000'
    HOST_04 = 'supv04:60000'

    def setUp(self):
        """ The setUp starts the subscriber to the Supvisors events and get the event queues. """
        # create a context
        self.context = Context()
        # create the thread of event subscriber
        self.zcontext = zmq.asyncio.Context.instance()
        self.logger = create_logger(logfile=r'./log/check_sequence.log')
        self.evloop = SequenceChecker(self.zcontext, self.logger)
        self.evloop.start()

    def tearDown(self):
        """ The tearDown stops the subscriber to the Supvisors events. """
        self.evloop.stop()
        # close resources
        self.logger.close()
        self.zcontext.term()

    def get_instances(self):
        """ Wait for instance_queue to put the list of active instances. """
        # 9 notifications are expected. if there's only one Supvisors instance, it may take up to 9*5=45 seconds
        try:
            self.identifiers = self.evloop.instance_queue.get(True, 40)
            self.assertGreater(len(self.identifiers), 0)
        except Empty:
            self.fail('failed to get the instances event in the last 40 seconds')

    def check_events(self, application_name=None):
        """ Receive and check events for processes and applications. """
        while self.context.has_events(application_name):
            # wait for a process event
            try:
                data = self.evloop.process_queue.get(True, 40)
            except Empty:
                self.fail('failed to get the expected events for this process')
            self.check_process_status(data)
            # wait for an application event
            try:
                data = self.evloop.application_queue.get(True, 2)
            except Empty:
                self.fail(f'failed to get the expected events for application={application_name}')
            self.check_application_event(data)

    def check_process_status(self, event):
        """ Check if the received process event corresponds to expectation. """
        self.evloop.logger.info(f'Checking process status: {event}')
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
        if type(state_event.statecode) is list:
            assert event['statename'] in state_event.statename
            assert event['statecode'] in state_event.statecode
        else:
            self.assertEqual(state_event.statename, event['statename'])
            self.assertEqual(state_event.statecode, event['statecode'])
        # check the running instances
        if state_event.statecode in [ProcessStates.STOPPING] + list(RUNNING_STATES):
            if state_event.identifiers:
                self.assertEqual(sorted(state_event.identifiers), sorted(event['identifiers']))
        program.identifiers = event['identifiers']
        # update program state
        program.state = event['statecode']
        program.expected_exit = event['expected_exit']

    def check_application_event(self, event):
        """ Check if the received application event corresponds to expectation. """
        # check that event corresponds to an expected application
        application_name = event['application_name']
        application = self.context.get_application(application_name)
        self.assertIsNotNone(application)
        self.evloop.logger.info(f'Checking application event={event} against {str(application)}')
        # check event contents in accordance with context
        if application.is_starting():
            self.assertDictContainsSubset({'statename': 'STARTING', 'statecode': ApplicationStates.STARTING.value},
                                          event)
        elif application.is_stopping():
            self.assertDictContainsSubset({'statename': 'STOPPING', 'statecode': ApplicationStates.STOPPING.value},
                                          event)
        elif application.is_running():
            self.assertDictContainsSubset({'statename': 'RUNNING', 'statecode': ApplicationStates.RUNNING.value},
                                          event)
        else:
            self.assertDictContainsSubset({'statename': 'STOPPED', 'statecode': ApplicationStates.STOPPED.value},
                                          event)
        self.assertEqual(application.get_failures(), (event['major_failure'], event['minor_failure']))

    def assertItemsEqual(self, lst1, lst2):
        """ Two lists are equal when they have the same size and when all elements of one are in the other one. """
        self.assertEqual(len(lst1), len(lst2))
        self.assertTrue(all(item in lst2 for item in lst1))
        self.assertTrue(all(item in lst1 for item in lst2))

    def assertDictContainsSubset(self, subset, origin, **kwargs):
        """ Create a dictionary with both and test that it's equal to origin. """
        self.assertEqual(dict(origin, **subset), origin)
