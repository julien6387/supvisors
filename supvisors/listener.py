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

import json
import time

from supervisor import events
from supervisor.datatypes import boolean
from supervisor.options import split_namespec

from supvisors.mainloop import SupvisorsMainLoop
from supvisors.ttypes import ProcessStates
from supvisors.utils import supvisors_shortcuts, InternalEventHeaders, RemoteCommEvents
from supvisors.supvisorszmq import SupervisorZmq


class SupervisorListener(object):
    """ This class subscribes directly to the internal Supervisor events.
    These events are published to all Supvisors instances.

    Attributes are:

        - supvisors: a reference to the Supvisors context,
        - address: the address name where this process is running,
        - main_loop: the Supvisors' event thread,
        - publisher: the ZeroMQ socket used to publish Supervisor events
        to all Supvisors threads.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # shortcuts for source code readability
        supvisors_shortcuts(self, ['fsm', 'info_source',
                                   'logger', 'statistician'])
        # test if statistics collector can be created for local host
        try:
            from supvisors.statscollector import instant_statistics
            self.collector = instant_statistics
        except ImportError:
            self.logger.warn('SupervisorListener.__init__: psutil not installed')
            self.logger.warn('SupervisorListener.__init__: this Supvisors will not publish statistics')
            self.collector = None
        # other attributes
        self.address = self.supvisors.address_mapper.local_address
        self.publisher = None
        self.main_loop = None
        # subscribe to internal events
        events.subscribe(events.SupervisorRunningEvent, self.on_running)
        events.subscribe(events.SupervisorStoppingEvent, self.on_stopping)
        events.subscribe(events.ProcessStateEvent, self.on_process)
        events.subscribe(events.Tick5Event, self.on_tick)
        events.subscribe(events.RemoteCommunicationEvent, self.on_remote_event)

    def on_running(self, _):
        """ Called when Supervisor is RUNNING.
        This method start the Supvisors main loop. """
        self.logger.info('SupervisorListener.on_running: local supervisord is RUNNING')
        # replace the default handler for web ui
        self.info_source.replace_default_handler()
        # update Supervisor internal data for extra_args
        self.info_source.prepare_extra_args()
        # create zmq sockets
        self.supvisors.zmq = SupervisorZmq(self.supvisors)
        # keep a reference to the internal events publisher
        self.publisher = self.supvisors.zmq.internal_publisher
        # start the main loop
        # env is needed to create XML-RPC proxy
        self.main_loop = SupvisorsMainLoop(self.supvisors)
        self.main_loop.start()

    def on_stopping(self, _):
        """ Called when Supervisor is STOPPING.
        This method stops the Supvisors main loop. """
        self.logger.warn('local supervisord is STOPPING')
        # force Supervisor to close HTTP servers
        # this will prevent any pending XML-RPC request to block the main loop
        self.info_source.close_httpservers()
        # stop the main loop
        self.logger.info('SupervisorListener.on_stopping: request to stop main loop')
        self.main_loop.stop()
        self.logger.info('SupervisorListener.on_stopping: end of main loop')
        # close zmq sockets
        self.supvisors.zmq.close()
        # unsubscribe from events
        events.clear()
        # finally, close logger
        # WARN: only if it is not the supervisor one
        if hasattr(self.logger, 'SUPVISORS'):
            self.logger.close()

    def on_process(self, event: events.ProcessStateEvent) -> None:
        """ Called when a ProcessEvent is sent by the local Supervisor.
        The event is published to all Supvisors instances. """
        event_name = events.getEventNameByType(event.__class__)
        self.logger.debug('SupervisorListener.on_process: got Process event from supervisord: {}'.format(event_name))
        # create payload from event
        payload = {'name': event.process.config.name,
                   'group': event.process.group.config.name,
                   'state': ProcessStates.from_string(event_name.split('_')[-1]),
                   'extra_args': event.process.config.extra_args,
                   'now': int(time.time()),
                   'pid': event.process.pid,
                   'expected': event.expected,
                   'spawnerr': event.process.spawnerr}
        self.logger.debug('SupervisorListener.on_process: payload={}'.format(payload))
        self.publisher.send_process_event(payload)

    def on_tick(self, event: events.TickEvent) -> None:
        """ Called when a TickEvent is notified.
        The event is published to all Supvisors instances.
        Then statistics are published and periodic task is triggered. """
        self.logger.debug('SupervisorListener.on_tick: got Tick event from supervisord: {}'.format(event.when))
        payload = {'when': event.when}
        self.publisher.send_tick_event(payload)
        # get and publish statistics at tick time (optional)
        if self.collector:
            status = self.supvisors.context.addresses[self.address]
            stats = self.collector(status.pid_processes())
            self.publisher.send_statistics(stats)
        # periodic task
        addresses = self.fsm.on_timer_event()
        # pushes isolated addresses to main loop
        self.supvisors.zmq.pusher.send_isolate_addresses(addresses)

    def on_remote_event(self, event: events.RemoteCommunicationEvent) -> None:
        """ Called when a RemoteCommunicationEvent is notified.
        This is used to sequence the events received from the Supvisors thread
        with the other events handled by the local Supervisor. """
        self.logger.debug('SupervisorListener.on_remote_event: got Remote event from supervisord: {} / {}'
                          .format(event.type, event.data))
        if event.type == RemoteCommEvents.SUPVISORS_AUTH:
            self.authorization(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_EVENT:
            self.unstack_event(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_INFO:
            self.unstack_info(event.data)

    def unstack_event(self, message: str):
        """ Unstack and process one event from the event queue. """
        event_type, event_address, event_data = json.loads(message)
        if event_type == InternalEventHeaders.TICK:
            self.logger.trace('SupervisorListener.unstack_event: got tick event from {}: {}'
                              .format(event_address, event_data))
            self.fsm.on_tick_event(event_address, event_data)
        elif event_type == InternalEventHeaders.PROCESS:
            self.logger.trace('SupervisorListener.unstack_event: got process event from {}: {}'
                              .format(event_address, event_data))
            self.fsm.on_process_event(event_address, event_data)
        elif event_type == InternalEventHeaders.STATISTICS:
            # this Supvisors could handle statistics
            # even if psutil is not installed
            self.logger.trace('SupervisorListener.unstack_event: got statistics event from {}: {}'
                              .format(event_address, event_data))
            self.statistician.push_statistics(event_address, event_data)

    def unstack_info(self, message: str):
        """ Unstack the process info received. """
        # unstack the queue for process info
        address_name, info = json.loads(message)
        self.logger.trace('SupervisorListener.unstack_info: got process info event from {}'.format(address_name))
        self.fsm.on_process_info(address_name, info)

    def authorization(self, data):
        """ Extract authorization and address from data and process event. """
        self.logger.trace('SupervisorListener.authorization: got authorization event: {}'.format(data))
        # split the line received
        address_name, authorized, master_address = tuple(x.split(':')[1] for x in data.split())
        self.fsm.on_authorization(address_name, boolean(authorized), master_address)

    def force_process_fatal(self, namespec: str):
        """ Publishes a fake process event showing a FATAL state for the process. """
        self.force_process_state(namespec, ProcessStates.FATAL)

    def force_process_unknown(self, namespec: str):
        """ Publishes a fake process event showing an UNKNOWN state for the process. """
        self.force_process_state(namespec, ProcessStates.UNKNOWN)

    def force_process_state(self, namespec: str, state: int):
        """ Publishes a fake process event showing a state for the process. """
        application_name, process_name = split_namespec(namespec)
        # create payload from event
        payload = {'processname': process_name,
                   'groupname': application_name,
                   'state': state,
                   'now': int(time.time()),
                   'pid': 0,
                   'expected': False}
        self.logger.debug('SupervisorListener.force_process_state: payload={}'.format(payload))
        self.publisher.send_process_event(payload)
