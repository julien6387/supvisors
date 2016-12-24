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

import time
import zmq

from supervisor import events
from supervisor.options import split_namespec
from supervisor.states import ProcessStates

from supvisors.mainloop import SupvisorsMainLoop
from supvisors.pool import SupvisorsPool
from supvisors.process import from_string
from supvisors.statistics import instant_statistics
from supvisors.utils import (EventHeaders, SUPVISORS_EVENT,
    SUPVISORS_INFO, SUPVISORS_TASK, supvisors_short_cuts)


class EventPublisher(object):
    """ This class is the wrapper of the ZeroMQ socket that publishes the events
    to the Supvisors instances.
    
    Attributes are:
    - supvisors: a reference to the Supervisor context,
    - address: the address name where this process is running,
    - socket: the ZeroMQ socket with a PUBLISH pattern, bound on the internal_port defined
        in the ['supvisors'] section of the Supervisor configuration file.
    """

    def __init__(self, supvisors, zmq_context):
        """ Initialization of the attributes. """
        # keep a reference to supvisors
        self.supvisors = supvisors
        # shortcuts for source code readability
        supvisors_short_cuts(self, ['logger'])
        self.address = self.supvisors.address_mapper.local_address
        # create ZMQ socket
        self.socket = zmq_context.socket(zmq.PUB)
        url = 'tcp://*:{}'.format(self.supvisors.options.internal_port)
        self.logger.info('binding EventPublisher to %s' % url)
        self.socket.bind(url)

    def send_tick_event(self, payload):
        """ Publishes the tick event with ZeroMQ. """
        self.logger.debug('send TickEvent {}'.format(payload))
        self.socket.send_pyobj((EventHeaders.TICK, self.address, payload))

    def send_process_event(self, payload):
        """ Publishes the process event with ZeroMQ. """
        self.logger.debug('send ProcessEvent {}'.format(payload))
        self.socket.send_pyobj((EventHeaders.PROCESS, self.address, payload))

    def send_statistics(self, payload):
        """ Publishes the statistics with ZeroMQ. """
        self.logger.debug('send Statistics {}'.format(payload))
        self.socket.send_pyobj((EventHeaders.STATISTICS, self.address, payload))


class SupervisorListener(object):
    """ This class subscribes directly to the internal Supervisor events.
    These events are published to all Supvisors instances.
    
    Attributes are:
    - supvisors: a reference to the Supvisors context,
    - address: the address name where this process is running,
    - main_loop: the Supvisors' event thread,
    - publisher: the ZeroMQ socket used to publish Supervisor events to all Supvisors threads.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # shortcuts for source code readability
        supvisors_short_cuts(self, ['logger'])
        self.address = self.supvisors.address_mapper.local_address
        # subscribe to internal events
        events.subscribe(events.SupervisorRunningEvent, self.on_running)
        events.subscribe(events.SupervisorStoppingEvent, self.on_stopping)
        events.subscribe(events.ProcessStateEvent, self.on_process)
        events.subscribe(events.Tick5Event, self.on_tick)
        events.subscribe(events.RemoteCommunicationEvent, self.on_remote_event)

    def on_running(self, event):
        """ Called when Supervisor is RUNNING.
        This method start the Supvisors main loop. """
        self.logger.info('local supervisord is RUNNING')
        # replace the default handler for web ui
        self.supvisors.info_source.replace_default_handler()
        # create pool for asynchronous requests
        self.supvisors.pool = SupvisorsPool(self.supvisors)
        # starts the main loop
        self.main_loop = SupvisorsMainLoop(self.supvisors)
        self.main_loop.start()
        # create publisher of Supervisor events
        self.publisher = EventPublisher(self.supvisors, self.main_loop.zmq_context)

    def on_stopping(self, event):
        """ Called when Supervisor is STOPPING.
        This method stops the Supvisors main loop. """
        self.logger.warn('local supervisord is STOPPING')
        # unsubscribe from events
        events.clear()
        # close zmq socket
        self.publisher.socket.close()
        # stop and join the main loop
        self.main_loop.stop()
        self.main_loop.join()
        # close the pool
        self.supvisors.pool.close()

    def on_process(self, event):
        """ Called when a ProcessEvent is sent by the local Supervisor.
        The event is published to all Supvisors instances. """
        event_name = events.getEventNameByType(event.__class__)
        self.logger.debug('got Process event from supervisord: {} {}'.format(event_name, event))
        # create payload from event
        payload = {'processname': event.process.config.name,
            'groupname': event.process.group.config.name,
            'state': from_string(event_name.split('_')[-1]),
            'now': int(time.time()), 
            'pid': event.process.pid,
            'expected': event.expected }
        self.logger.debug('payload={}'.format(payload))
        self.publisher.send_process_event(payload)

    def on_tick(self, event):
        """ Called when a TickEvent is notified.
        The event is published to all Supvisors instances.
        Statistics are also published. """
        self.logger.debug('got Tick event from supervisord: {}'.format(event))
        payload = {'when': event.when}
        self.publisher.send_tick_event(payload)
        # get and publish statistics at tick time
        status = self.supvisors.context.addresses[self.address]
        self.publisher.send_statistics(instant_statistics(status.pid_processes()))

    def on_remote_event(self, event):
        """ Called when a RemoteCommunicationEvent is notified.
        This is used to sequence the events received from the Supvisors thread
        with the other events handled by the local Supervisor."""
        if event.type == SUPVISORS_EVENT:
            self.main_loop.unstack_event()
        elif event.type == SUPVISORS_INFO:
            self.main_loop.unstack_info()
        elif event.type == SUPVISORS_TASK:
            self.main_loop.periodic_task()

    def force_process_fatal(self, namespec):
        """ Publishes a fake process event showing a FATAL state for the process. """
        application_name, process_name = split_namespec(namespec)
        # create payload from event
        payload = {'processname': process_name,
            'groupname': application_name,
            'state': ProcessStates.FATAL,
            'now': int(time.time()), 
            'pid': 0,
            'expected': False}
        self.logger.debug('payload={}'.format(payload))
        self.publisher.send_process_event(payload)
