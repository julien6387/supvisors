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

import json
import time

from supervisor import events
from supervisor.datatypes import boolean
from supervisor.options import split_namespec

from supvisors.mainloop import SupvisorsMainLoop
from supvisors.statistics import instant_statistics
from supvisors.ttypes import ProcessStates
from supvisors.utils import (supvisors_short_cuts, InternalEventHeaders, RemoteCommEvents)
from supvisors.supvisorszmq import SupvisorsZmq


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
        supvisors_short_cuts(self, ['fsm', 'info_source', 'logger', 'statistician'])
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
        self.info_source.replace_default_handler()
        # create zmq sockets
        self.supvisors.zmq = SupvisorsZmq(self.supvisors)
        # keep a reference to the internal events publisher
        self.publisher = self.supvisors.zmq.internal_publisher
        # start the main loop
        self.main_loop = SupvisorsMainLoop(self.supvisors)
        self.main_loop.start()

    def on_stopping(self, event):
        """ Called when Supervisor is STOPPING.
        This method stops the Supvisors main loop. """
        self.logger.warn('local supervisord is STOPPING')
        # unsubscribe from events
        events.clear()
        # force Supervisor to close HTTP servers
        self.info_source.close_httpservers()
        # stop and join the main loop
        self.main_loop.stop()
        # close zmq sockets
        self.supvisors.zmq.close()
        # finally, close logger
        self.logger.close()

    def on_process(self, event):
        """ Called when a ProcessEvent is sent by the local Supervisor.
        The event is published to all Supvisors instances. """
        event_name = events.getEventNameByType(event.__class__)
        self.logger.debug('got Process event from supervisord: {} {}'.format(event_name, event))
        # create payload from event
        payload = {'processname': event.process.config.name,
            'groupname': event.process.group.config.name,
            'state': ProcessStates._from_string(event_name.split('_')[-1]),
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
        if event.type == RemoteCommEvents.SUPVISORS_AUTH:
            self.authorization(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_EVENT:
            self.unstack_event(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_INFO:
            self.unstack_info(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_TASK:
            self.periodic_task()

    def unstack_event(self, message):
        """ Unstack and process one event from the event queue. """
        event_type, event_address, event_data = json.loads(message)
        if event_type == InternalEventHeaders.TICK:
            self.logger.blather('got tick event from {}: {}'.format(event_address, event_data))
            self.fsm.on_tick_event(event_address, event_data)
        elif event_type == InternalEventHeaders.PROCESS:
            self.logger.blather('got process event from {}: {}'.format(event_address, event_data))
            self.fsm.on_process_event(event_address, event_data)
        elif event_type == InternalEventHeaders.STATISTICS:
            self.logger.blather('got statistics event from {}: {}'.format(event_address, event_data))
            self.statistician.push_statistics(event_address, event_data)

    def unstack_info(self, message):
        """ Unstack the process info received. """
        # unstack the queue for process info
        address_name, info = json.loads(message)
        self.logger.blather('got process info event from {}'.format(address_name))
        self.fsm.on_process_info(address_name, info)

    def authorization(self, data):
        """ Extract authorization and address from data and process event. """
        self.logger.blather('got authorization event: {}'.format(data))
        # split the line received
        address_name, authorized = tuple(x.split(':')[1] for x in data.split())
        self.fsm.on_authorization(address_name, boolean(authorized))

    def periodic_task(self):
        """ Periodic task that mainly checks that addresses are still operating. """
        self.logger.blather('got periodic task event')
        addresses = self.fsm.on_timer_event()
        # pushes isolated addresses to main loop
        self.supvisors.zmq.pusher.send_isolate_addresses(addresses)

    def force_process_fatal(self, namespec):
        """ Publishes a fake process event showing a FATAL state for the process. """
        self.force_process_state(ProcessStates.FATAL)

    def force_process_unknown(self, namespec):
        """ Publishes a fake process event showing an UNKNOWN state for the process. """
        self.force_process_state(ProcessStates.UNKNOWN)

    def force_process_state(self, namespec, state):
        """ Publishes a fake process event showing a state for the process. """
        application_name, process_name = split_namespec(namespec)
        # create payload from event
        payload = {'processname': process_name,
            'groupname': application_name,
            'state': state,
            'now': int(time.time()), 
            'pid': 0,
            'expected': False}
        self.logger.debug('payload={}'.format(payload))
        self.publisher.send_process_event(payload)
