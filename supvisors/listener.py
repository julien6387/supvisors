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
from supervisor.options import make_namespec
from supervisor.states import ProcessStates, _process_states_by_code
from supervisor.xmlrpc import RPCError

from .mainloop import SupvisorsMainLoop
from .process import ProcessStatus
from .supvisorszmq import SupervisorZmq, RequestPusher
from .ttypes import SupvisorsStates, ProcessEvent, ProcessAddedEvent, ProcessRemovedEvent
from .utils import InternalEventHeaders, RemoteCommEvents

# get reverted map for ProcessStates
_process_states_by_name = {y: x for x, y in _process_states_by_code.items()}


def add_process_events() -> None:
    """ Register new events in Supervisor EventTypes.
    The new events are in support of Supervisor issue #177.

    :return: None
    """
    events.register('PROCESS', ProcessEvent)  # abstract
    events.register('PROCESS_ADDED', ProcessAddedEvent)
    events.register('PROCESS_REMOVED', ProcessRemovedEvent)


class SupervisorListener(object):
    """ This class subscribes directly to the internal Supervisor events.
    These events are published to all Supvisors instances.

    Attributes are:

        - supvisors: the Supvisors global structure ;
        - logger: the Supvisors logger ;
        - collector: the statistics compiler ;
        - local_identifier: the identifier of the local Supvisors instance ;
        - pusher: the ZeroMQ socket used to publish Supvisors internal events to all Supvisors instances ;
        - main_loop: the Supvisors' event thread.
    """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        # test if statistics collector can be created for local host
        self.collector = None
        try:
            from .statscollector import instant_statistics
            self.collector = instant_statistics
        except ImportError:
            self.logger.info('SupervisorListener: psutil not installed')
            self.logger.warn('SupervisorListener: this Supvisors instance cannot not collect statistics')
        # other attributes
        self.local_identifier: str = supvisors.supvisors_mapper.local_identifier
        self.pusher: Optional[RequestPusher] = None
        self.main_loop: Optional[SupvisorsMainLoop] = None
        # add new events to Supervisor EventTypes
        add_process_events()
        # subscribe to internal events
        events.subscribe(events.SupervisorRunningEvent, self.on_running)
        events.subscribe(events.SupervisorStoppingEvent, self.on_stopping)
        events.subscribe(events.ProcessStateEvent, self.on_process_state)
        events.subscribe(ProcessAddedEvent, self.on_process_added)
        events.subscribe(ProcessRemovedEvent, self.on_process_removed)
        events.subscribe(events.ProcessGroupAddedEvent, self.on_group_added)
        events.subscribe(events.Tick5Event, self.on_tick)
        events.subscribe(events.RemoteCommunicationEvent, self.on_remote_event)

    def on_running(self, _):
        """ Called when Supervisor is RUNNING.
        This method start the Supvisors main loop. """
        self.logger.info('SupervisorListener.on_running: local supervisord is RUNNING')
        # replace the default handler for web ui
        self.supvisors.supervisor_data.replace_default_handler()
        # update Supervisor internal data for extra_args
        # WARN: this is also triggered by adding groups in Supervisor, however the initial group added events are sent
        # before the Supvisors RPC interface is created
        self.supvisors.supervisor_data.prepare_extra_args()
        # create zmq sockets
        self.supvisors.zmq = SupervisorZmq(self.supvisors)
        # keep a reference to the internal pusher used to defer the events publication
        self.pusher = self.supvisors.zmq.pusher
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
        self.supvisors.supervisor_data.close_httpservers()
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

    def on_process_state(self, event: events.ProcessStateEvent) -> None:
        """ Called when a ProcessStateEvent is sent by the local Supervisor.
        The event is published to all Supvisors instances. """
        event_name = events.getEventNameByType(event.__class__)
        process_config = event.process.config
        namespec = make_namespec(event.process.group.config.name, process_config.name)
        self.logger.debug(f'SupervisorListener.on_process_state: got {event_name} for {namespec}')
        # create payload from event
        payload = {'name': process_config.name,
                   'group': event.process.group.config.name,
                   'state': _process_states_by_name[event_name.split('_')[-1]],
                   'now': int(time.time()),
                   'pid': event.process.pid,
                   'expected': event.expected,
                   'spawnerr': event.process.spawnerr}
        if hasattr(process_config, 'extra_args'):
            payload['extra_args'] = process_config.extra_args
        self.logger.trace(f'SupervisorListener.on_process_state: payload={payload}')
        self.pusher.send_process_state_event(payload)

    def on_process_added(self, event: ProcessAddedEvent) -> None:
        """ Called when a process has been added due to a numprocs change.

        :param event: the ProcessAddedEvent object
        :return: None
        """
        namespec = make_namespec(event.process.group.config.name, event.process.config.name)
        self.logger.debug('SupervisorListener.on_process_added: got ProcessAddedEvent for {namespec}')
        # use Supervisor to get local information on all processes
        rpc_intf = self.supvisors.supervisor_data.supvisors_rpc_interface
        try:
            process_info = rpc_intf.get_local_process_info(namespec)
        except RPCError as e:
            self.logger.error(f'SupervisorListener.on_process_added: failed to get process info for {namespec}:'
                              f' {e.text}')
        else:
            self.logger.trace(f'SupervisorListener.on_process_added: process_info={process_info}')
            self.pusher.send_process_added_event(process_info)

    def on_process_removed(self, event: ProcessRemovedEvent) -> None:
        """ Called when a process has been removed due to a numprocs change.

        :param event: the ProcessRemovedEvent object
        :return: None
        """
        namespec = make_namespec(event.process.group.config.name, event.process.config.name)
        self.logger.debug(f'SupervisorListener.on_process_removed: got ProcessRemovedEvent for {namespec}')
        payload = {'name': event.process.config.name, 'group': event.process.group.config.name}
        self.logger.trace(f'SupervisorListener.on_process_removed: payload={payload}')
        self.pusher.send_process_removed_event(payload)

    def on_group_added(self, event: events.ProcessGroupAddedEvent) -> None:
        """ Called when a group has been added due to a Supervisor configuration update.

        :param event: the ProcessGroupAddedEvent object
        :return: None
        """
        # update Supervisor internal data for extra_args
        self.logger.debug(f'SupervisorListener.on_group_added: group={event.group}')
        self.supvisors.supervisor_data.prepare_extra_args(event.group)

    def on_tick(self, event: events.TickEvent) -> None:
        """ Called when a TickEvent is notified.
        The event is published to all Supvisors instances.
        Then statistics are published and periodic task is triggered.

        :param event: the Supervisor TICK event
        :return: None
        """
        self.logger.debug('SupervisorListener.on_tick: got TickEvent from Supervisor')
        payload = {'when': event.when}
        self.logger.trace(f'SupervisorListener.on_tick: payload={payload}')
        self.pusher.send_tick_event(payload)
        # get and publish statistics at tick time (optional)
        if self.collector and self.supvisors.options.stats_enabled:
            status = self.supvisors.context.instances[self.local_identifier]
            stats = self.collector(status.pid_processes())
            self.pusher.send_statistics(stats)

    def on_remote_event(self, event: events.RemoteCommunicationEvent) -> None:
        """ Called when a RemoteCommunicationEvent is notified.
        This is used to sequence the events received from the Supvisors thread with the other events handled
        by the local Supervisor. """
        self.logger.trace(f'SupervisorListener.on_remote_event: got RemoteCommunicationEvent {event.type}'
                          f' / {event.data}')
        if event.type == RemoteCommEvents.SUPVISORS_AUTH:
            self.authorization(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_EVENT:
            self.unstack_event(event.data)
        elif event.type == RemoteCommEvents.SUPVISORS_INFO:
            self.unstack_info(event.data)

    def unstack_event(self, message: str):
        """ Unstack and process one event from the event queue. """
        event_type, (event_identifier, event_data) = json.loads(message)
        if event_type == InternalEventHeaders.TICK.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got TICK from {event_identifier}: {event_data}')
            self.supvisors.fsm.on_tick_event(event_identifier, event_data)
        elif event_type == InternalEventHeaders.PROCESS.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got PROCESS from {event_identifier}: {event_data}')
            self.supvisors.fsm.on_process_state_event(event_identifier, event_data)
        elif event_type == InternalEventHeaders.PROCESS_ADDED.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got PROCESS_ADDED from {event_identifier}:'
                              f' {event_data}')
            self.supvisors.fsm.on_process_added_event(event_identifier, event_data)
        elif event_type == InternalEventHeaders.PROCESS_REMOVED.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got PROCESS_REMOVED from {event_identifier}:'
                              f' {event_data}')
            self.supvisors.fsm.on_process_removed_event(event_identifier, event_data)
        elif event_type == InternalEventHeaders.STATISTICS.value:
            # this Supvisors could handle statistics even if psutil is not installed
            # unless the function is explicitly disabled
            self.logger.trace(f'SupervisorListener.unstack_event: got STATISTICS from {event_identifier}: {event_data}')
            if self.supvisors.options.stats_enabled:
                self.supvisors.statistician.push_statistics(event_identifier, event_data)
        elif event_type == InternalEventHeaders.STATE.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got STATE from {event_identifier}')
            self.supvisors.fsm.on_state_event(event_identifier, event_data)

    def unstack_info(self, message: str):
        """ Unstack the process info received. """
        # unstack the queue for process info
        identifier, info = json.loads(message)
        self.logger.trace(f'SupervisorListener.unstack_info: got process info event from {identifier}')
        self.supvisors.fsm.on_process_info(identifier, info)

    def authorization(self, data):
        """ Extract authorization and identifier from data and process event. """
        self.logger.trace(f'SupervisorListener.authorization: got authorization event: {data}')
        # split the line received
        identifier, authorized_string, master_identifier, supvisors_state = tuple(x.split('=')[1] for x in data.split())
        authorized = boolean(authorized_string) if authorized_string != 'None' else None
        self.supvisors.fsm.on_authorization(identifier, authorized, master_identifier, SupvisorsStates[supvisors_state])

    def force_process_state(self, process: ProcessStatus, expected_state: ProcessStates, identifier: str,
                            forced_state: ProcessStates, reason: str) -> None:
        """ Publish the process state requested to all Supvisors instances.

        :param process: the process structure
        :param expected_state: the process state expected
        :param identifier: the identifier of the Supvisors instance where the process state is expected
        :param forced_state: the process state to force if the expected state has not been received
        :param reason: the reason declared
        :return: None
        """
        # create payload from event
        payload = {'group': process.application_name, 'name': process.process_name, 'state': expected_state,
                   'forced_state': forced_state, 'identifier': identifier,
                   'now': int(time.time()), 'pid': 0, 'expected': False, 'spawnerr': reason,
                   'extra_args': process.extra_args}
        self.logger.debug(f'SupervisorListener.force_process_state: payload={payload}')
        self.pusher.send_process_state_event(payload)
