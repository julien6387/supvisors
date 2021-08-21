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

from typing import Any, Optional

from supervisor import events
from supervisor.datatypes import boolean
from supervisor.loggers import Logger
from supervisor.options import split_namespec
from supervisor.states import ProcessStates, _process_states_by_code

from .mainloop import SupvisorsMainLoop
from .supvisorszmq import SupervisorZmq, InternalEventPublisher
from .ttypes import SupvisorsStates
from .utils import InternalEventHeaders, RemoteCommEvents

# get reverted map for ProcessStates
_process_states_by_name = {y: x for x, y in _process_states_by_code.items()}


class SupervisorListener(object):
    """ This class subscribes directly to the internal Supervisor events.
    These events are published to all Supvisors instances.

    Attributes are:

        - supvisors: a reference to the Supvisors global structure ;
        - logger: a reference to the Supvisors logger ;
        - collector: the statistics compiler ;
        - local_node_name: the node name where this process is running ;
        - sequence_counter: the counter for TICK events ;
        - publisher: the ZeroMQ socket used to publish Supervisor events to all Supvisors threads ;
        - main_loop: the Supvisors' event thread.
    """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # test if statistics collector can be created for local host
        try:
            from supvisors.statscollector import instant_statistics
        except ImportError:
            self.logger.warn('SupervisorListener.init: psutil not installed')
            self.logger.warn('SupervisorListener.init: this Supvisors will not publish statistics')
            instant_statistics = None
        self.collector = instant_statistics
        # other attributes
        self.local_node_name: str = self.supvisors.address_mapper.local_node_name
        self.sequence_counter: int = 0
        self.publisher: Optional[InternalEventPublisher] = None
        self.main_loop: Optional[SupvisorsMainLoop] = None
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
        self.supvisors.info_source.replace_default_handler()
        # update Supervisor internal data for extra_args
        self.supvisors.info_source.prepare_extra_args()
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
        self.supvisors.info_source.close_httpservers()
        # stop the main loop
        self.logger.info('SupervisorListener.on_stopping: request to stop main loop')
        self.main_loop.stop()
        self.logger.info('SupervisorListener.on_stopping: end of main loop')
        # close zmq sockets
        self.supvisors.zmq.close()
        # unsubscribe from events
        events.clear()
        # finally, close logger
        # WARN: only if it is not the supervisor logger
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
                   'state': _process_states_by_name[event_name.split('_')[-1]],
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
        self.sequence_counter += 1
        payload = {'sequence_counter': self.sequence_counter, 'when': event.when}
        self.logger.debug('SupervisorListener.on_tick: got Tick event from supervisord: {}'.format(payload))
        self.publisher.send_tick_event(payload)
        # get and publish statistics at tick time (optional)
        if self.collector:
            status = self.supvisors.context.nodes[self.local_node_name]
            stats = self.collector(status.pid_processes())
            self.publisher.send_statistics(stats)
        # periodic task
        node_names = self.supvisors.fsm.on_timer_event()
        # send isolated nodes to main loop
        self.supvisors.zmq.pusher.send_isolate_nodes(node_names)

    def on_remote_event(self, event: events.RemoteCommunicationEvent) -> None:
        """ Called when a RemoteCommunicationEvent is notified.
        This is used to sequence the events received from the Supvisors thread with the other events handled
        by the local Supervisor. """
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
        event_type, event_node, event_data = json.loads(message)
        if event_type == InternalEventHeaders.TICK.value:
            self.logger.trace('SupervisorListener.unstack_event: got tick event from {}: {}'
                              .format(event_node, event_data))
            self.supvisors.fsm.on_tick_event(event_node, event_data)
        elif event_type == InternalEventHeaders.PROCESS.value:
            self.logger.trace('SupervisorListener.unstack_event: got process event from {}: {}'
                              .format(event_node, event_data))
            self.supvisors.fsm.on_process_event(event_node, event_data)
        elif event_type == InternalEventHeaders.STATISTICS.value:
            # this Supvisors could handle statistics even if psutil is not installed
            self.logger.trace('SupervisorListener.unstack_event: got statistics event from {}: {}'
                              .format(event_node, event_data))
            self.supvisors.statistician.push_statistics(event_node, event_data)
        elif event_type == InternalEventHeaders.STATE.value:
            self.logger.trace('SupervisorListener.unstack_event: got OPERATION event from {}'
                              .format(event_node))
            self.supvisors.fsm.on_state_event(event_node, event_data)

    def unstack_info(self, message: str):
        """ Unstack the process info received. """
        # unstack the queue for process info
        node_name, info = json.loads(message)
        self.logger.trace('SupervisorListener.unstack_info: got process info event from {}'.format(node_name))
        self.supvisors.fsm.on_process_info(node_name, info)

    def authorization(self, data):
        """ Extract authorization and node name from data and process event. """
        self.logger.trace('SupervisorListener.authorization: got authorization event: {}'.format(data))
        # split the line received
        node_name, authorized, master_node_name, supvisors_state = tuple(x.split(':')[1] for x in data.split())
        self.supvisors.fsm.on_authorization(node_name, boolean(authorized), master_node_name,
                                            SupvisorsStates[supvisors_state])

    def force_process_state(self, namespec: str, state: ProcessStates, reason: str) -> None:
        """ Publish the process state requested to all Supvisors instances.

        :param namespec: the process namespec
        :param state: the process state to force
        :param reason: the reason declared
        :return: None
        """
        # create payload from event
        application_name, process_name = split_namespec(namespec)
        payload = {'group': application_name, 'name': process_name, 'state': state, 'forced': True,
                   'now': int(time.time()), 'pid': 0, 'expected': False, 'spawnerr': reason}
        # get extra_args if process is known to local Supervisor
        try:
            payload['extra_args'] = self.supvisors.info_source.get_extra_args(namespec)
        except KeyError:
            self.logger.trace('SupervisorListener.force_process_state: cannot get extra_args from namespec={}'
                              ' because the program is unknown to local Supervisor'.format(namespec))
        self.logger.debug('SupervisorListener.force_process_state: payload={}'.format(payload))
        self.publisher.send_process_event(payload)
