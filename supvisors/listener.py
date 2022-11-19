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
from traceback import format_exc
from typing import Any, Optional, Union

from supervisor import events
from supervisor.loggers import Logger
from supervisor.options import make_namespec
from supervisor.states import ProcessStates, _process_states_by_code
from supervisor.xmlrpc import RPCError

from .mainloop import SupvisorsMainLoop
from .process import ProcessStatus
from .publisherinterface import create_external_publisher
from .supvisorssocket import SupvisorsSockets, InternalPublisher
from .ttypes import (ProcessEvent, ProcessAddedEvent, ProcessRemovedEvent, ProcessEnabledEvent, ProcessDisabledEvent,
                     InternalEventHeaders, RemoteCommEvents, Payload)

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
    events.register('PROCESS_ENABLED', ProcessEnabledEvent)
    events.register('PROCESS_DISABLED', ProcessDisabledEvent)


class SupervisorListener(object):
    """ This class subscribes directly to the internal Supervisor events.
    These events are published to all Supvisors instances.

    Attributes are:

        - supvisors: the Supvisors global structure ;
        - logger: the Supvisors logger ;
        - collector: the statistics compiler ;
        - local_identifier: the identifier of the local Supvisors instance ;
        - publisher: the socket used to publish Supvisors internal events to all Supvisors instances ;
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
        self.counter = 0
        # WARN: the SupvisorsMainLoop cannot be created at this level
        # Before running, Supervisor forks when daemonized and the sockets are then lost
        self.main_loop: Optional[SupvisorsMainLoop] = None
        self.publisher: Optional[InternalPublisher] = None
        # add new events to Supervisor EventTypes
        add_process_events()
        # subscribe to internal events
        events.subscribe(events.SupervisorRunningEvent, self.on_running)
        events.subscribe(events.SupervisorStoppingEvent, self.on_stopping)
        events.subscribe(events.ProcessStateEvent, self.on_process_state)
        events.subscribe(ProcessAddedEvent, self.on_process_added)
        events.subscribe(ProcessRemovedEvent, self.on_process_removed)
        events.subscribe(ProcessEnabledEvent, self.on_process_disability)
        events.subscribe(ProcessDisabledEvent, self.on_process_disability)
        events.subscribe(events.ProcessGroupAddedEvent, self.on_group_added)
        events.subscribe(events.ProcessGroupRemovedEvent, self.on_group_removed)
        events.subscribe(events.Tick5Event, self.on_tick)
        events.subscribe(events.RemoteCommunicationEvent, self.on_remote_event)

    def on_running(self, _):
        """ Called when Supervisor is RUNNING.
        This method start the Supvisors main loop. """
        self.logger.info('SupervisorListener.on_running: local supervisord is RUNNING')
        try:
            # reset the tick counter
            self.counter = 0
            # update Supervisor internal data for Supvisors support
            self.supvisors.supervisor_data.update_supervisor()
            # create the Supvisors communication structures
            self.supvisors.sockets = SupvisorsSockets(self.supvisors)
            self.supvisors.external_publisher = create_external_publisher(self.supvisors)
            # keep a reference to the internal publisher used to share the events publication
            self.publisher = self.supvisors.sockets.publisher
            # At this point, Supervisor has forked if necessary so the main loop can be started
            self.main_loop = SupvisorsMainLoop(self.supvisors)
            self.logger.debug('SupervisorListener.on_running: request to start main loop')
            self.main_loop.start()
            self.logger.debug('SupervisorListener.on_running: main loop started')
            # Trigger the FSM
            self.supvisors.fsm.next()
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_running: {format_exc()}')

    def on_stopping(self, _):
        """ Called when Supervisor is STOPPING.
        This method stops the Supvisors main loop. """
        self.logger.warn('SupervisorListener.on_stopping: local supervisord is STOPPING')
        try:
            # force Supervisor to close HTTP servers
            # this will prevent any pending XML-RPC request to block the main loop
            self.supvisors.supervisor_data.close_httpservers()
            # close external publication
            if self.supvisors.external_publisher:
                self.logger.debug('SupervisorListener.on_stopping: stopping external publication thread')
                self.supvisors.external_publisher.close()
                self.logger.debug('SupervisorListener.on_stopping: external publication thread stopped')
            # stop the main loop
            self.logger.debug('SupervisorListener.on_stopping: stopping main loop')
            self.main_loop.stop()
            self.logger.debug('SupervisorListener.on_stopping: main loop stopped')
            # close pusher and publication sockets
            self.logger.debug('SupervisorListener.on_stopping: stopping internal publication thread')
            self.supvisors.sockets.stop()
            self.logger.debug('SupervisorListener.on_stopping: internal publication thread stopped')
            # unsubscribe from events
            events.clear()
            # finally, close logger
            # WARN: only if it is not the supervisor logger
            if hasattr(self.logger, 'SUPVISORS'):
                self.logger.close()
        except Exception as exc:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_stopping: {format_exc()}')

    def on_process_state(self, event: events.ProcessStateEvent) -> None:
        """ Called when a ProcessStateEvent is sent by the local Supervisor.
        The event is published to all Supvisors instances. """
        try:
            event_name = events.getEventNameByType(event.__class__)
            process_config = event.process.config
            namespec = make_namespec(event.process.group.config.name, process_config.name)
            self.logger.debug(f'SupervisorListener.on_process_state: got {event_name} for {namespec}')
            # create payload from event
            payload = {'name': process_config.name,
                       'group': event.process.group.config.name,
                       'state': _process_states_by_name[event_name.split('_')[-1]],
                       'now': time.time(),
                       'pid': event.process.pid,
                       'expected': event.expected,
                       'spawnerr': event.process.spawnerr,
                       'extra_args': process_config.extra_args,
                       'disabled': process_config.disabled}
            self.logger.trace(f'SupervisorListener.on_process_state: payload={payload}')
            self.publisher.send_process_state_event(payload)
        except Exception as exc:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_state: {format_exc()}')

    def _get_local_process_info(self, namespec: str) -> Payload:
        """ Use the Supvisors RPCInterface to get local information on this process.

        :param namespec: the process namespec
        :return: the process local information
        """
        #
        try:
            rpc_intf = self.supvisors.supervisor_data.supvisors_rpc_interface
            return rpc_intf.get_local_process_info(namespec)
        except RPCError as e:
            self.logger.error(f'SupervisorListener.get_local_process_info: failed to get process info for {namespec}:'
                              f' {e.text}')

    def on_process_added(self, event: ProcessAddedEvent) -> None:
        """ Called when a process has been added due to a numprocs change.

        :param event: the ProcessAddedEvent object
        :return: None
        """
        try:
            namespec = make_namespec(event.process.group.config.name, event.process.config.name)
            self.logger.debug(f'SupervisorListener.on_process_added: got ProcessAddedEvent for {namespec}')
            # use RPCInterface to get local information on this process
            process_info = self._get_local_process_info(namespec)
            if process_info:
                self.logger.trace(f'SupervisorListener.on_process_added: process_info={process_info}')
                self.publisher.send_process_added_event([process_info])
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_added: {format_exc()}')

    def on_process_removed(self, event: ProcessRemovedEvent) -> None:
        """ Called when a process has been removed due to a numprocs change.

        :param event: the ProcessRemovedEvent object
        :return: None
        """
        try:
            namespec = make_namespec(event.process.group.config.name, event.process.config.name)
            self.logger.debug(f'SupervisorListener.on_process_removed: got ProcessRemovedEvent for {namespec}')
            payload = {'name': event.process.config.name, 'group': event.process.group.config.name}
            self.logger.trace(f'SupervisorListener.on_process_removed: payload={payload}')
            self.publisher.send_process_removed_event(payload)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_removed: {format_exc()}')

    def on_process_disability(self, event: Union[ProcessEnabledEvent, ProcessDisabledEvent]) -> None:
        """ Called when a process has been enabled or disabled.

        :param event: the ProcessEnabledEvent or ProcessDisabledEvent object
        :return: None
        """
        try:
            namespec = make_namespec(event.process.group.config.name, event.process.config.name)
            self.logger.debug('SupervisorListener.on_process_disability: got ProcessEnabledEvent or'
                              f' ProcessDisabledEvent for {namespec}')
            # use RPCInterface to get local information on this process
            process_info = self._get_local_process_info(namespec)
            if process_info:
                self.logger.trace(f'SupervisorListener.on_process_disability: process_info={process_info}')
                self.publisher.send_process_disability_event(process_info)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_disability: {format_exc()}')

    def on_group_added(self, event: events.ProcessGroupAddedEvent) -> None:
        """ Called when a group has been added following a Supervisor configuration update.
        This method performs an update of the internal data structure and sends a process payload
        to all other Supvisors instances.

        :param event: the ProcessGroupAddedEvent object
        :return: None
        """
        try:
            self.logger.debug(f'SupervisorListener.on_group_added: group={event.group}')
            # update Supervisor internal data for extra_args
            self.supvisors.supervisor_data.update_internal_data(event.group)
            # inform all Supvisors instances that new processes have been added
            group_process_info = []
            for process_name in self.supvisors.supervisor_data.get_group_processes(event.group):
                namespec = make_namespec(event.group, process_name)
                # use RPCInterface to get local information on this process
                process_info = self._get_local_process_info(namespec)
                if process_info:
                    self.logger.trace(f'SupervisorListener.on_process_added: process_info={process_info}')
                    group_process_info.append(process_info)
            self.publisher.send_process_added_event(group_process_info)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_group_added: {format_exc()}')

    def on_group_removed(self, event: events.ProcessGroupRemovedEvent) -> None:
        """ Called when a group has been removed following a Supervisor configuration update.
        Unlike the ProcessGroupAddedEvent case, Supervisor does not send anything else so other Supvisors instances
        must be informed.

        :param event: the ProcessGroupRemovedEvent object
        :return: None
        """
        try:
            # reuse existing event for process removed event
            self.logger.debug(f'SupervisorListener.on_group_removed: group={event.group}')
            payload = {'name': '*', 'group': event.group}
            self.logger.trace(f'SupervisorListener.on_process_removed: payload={payload}')
            self.publisher.send_process_removed_event(payload)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_group_removed: {format_exc()}')

    def on_tick(self, event: events.TickEvent) -> None:
        """ Called when a TickEvent is notified.
        The event is published to all Supvisors instances.
        Then statistics are published and periodic task is triggered.

        :param event: the Supervisor TICK event
        :return: None
        """
        try:
            self.logger.debug(f'SupervisorListener.on_tick: got TickEvent from Supervisor {event}')
            # reset the time information to get more resolution
            payload = {'when': time.time(), 'sequence_counter': self.counter}
            self.counter += 1
            self.logger.trace(f'SupervisorListener.on_tick: payload={payload}')
            self.publisher.send_tick_event(payload)
            # get and publish statistics at tick time (optional)
            if self.collector and self.supvisors.options.stats_enabled:
                status = self.supvisors.context.instances[self.local_identifier]
                stats = self.collector(status.pid_processes())
                self.publisher.send_statistics(stats)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_tick: {format_exc()}')

    def on_remote_event(self, event: events.RemoteCommunicationEvent) -> None:
        """ Called when a RemoteCommunicationEvent is notified.
        This is used to sequence the events received from the Supvisors thread with the other events handled
        by the local Supervisor. """
        try:
            self.logger.trace(f'SupervisorListener.on_remote_event: got RemoteCommunicationEvent {event.type}'
                              f' / {event.data}')
            if event.type == RemoteCommEvents.SUPVISORS_AUTH.value:
                self.authorization(event.data)
            elif event.type == RemoteCommEvents.SUPVISORS_EVENT.value:
                self.unstack_event(event.data)
            elif event.type == RemoteCommEvents.SUPVISORS_INFO.value:
                self.unstack_info(event.data)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_remote_event: {format_exc()}')

    def unstack_event(self, message: str):
        """ Unstack and process one event from the event queue. """
        event_type, (event_identifier, event_data) = json.loads(message)
        if event_type == InternalEventHeaders.HEARTBEAT.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got HEARTBEAT from {event_identifier}')
            # NOTE: at the moment, Supvisors still relies on the TICK to identify a node disconnection
            #  if more reactivity is needed at some point, the HEARTBEAT could be used
            # self.supvisors.fsm.on_tick_event(event_identifier, event_data)
        elif event_type == InternalEventHeaders.TICK.value:
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
        elif event_type == InternalEventHeaders.PROCESS_DISABILITY.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got PROCESS_DISABILITY from {event_identifier}:'
                              f' {event_data}')
            self.supvisors.fsm.on_process_disability_event(event_identifier, event_data)
        elif event_type == InternalEventHeaders.STATISTICS.value:
            # this Supvisors could handle statistics even if psutil is not installed
            self.logger.trace(f'SupervisorListener.unstack_event: got STATISTICS from {event_identifier}: {event_data}')
            self.supvisors.statistician.push_statistics(event_identifier, event_data)
        elif event_type == InternalEventHeaders.STATE.value:
            self.logger.trace(f'SupervisorListener.unstack_event: got STATE from {event_identifier}')
            self.supvisors.fsm.on_state_event(event_identifier, event_data)

    def unstack_info(self, message: str) -> None:
        """ Unstack the process info received.

        :param message: the JSON message received.
        :return: None
        """
        # unstack the queue for process info
        identifier, info = json.loads(message)
        self.logger.trace(f'SupervisorListener.unstack_info: got process info event from {identifier}')
        self.supvisors.fsm.on_process_info(identifier, info)

    def authorization(self, message: str) -> None:
        """ Extract authorization and identifier from data and process event. """
        identifier, authorized, master_identifier = json.loads(message)
        self.logger.trace(f'SupervisorListener.authorization: got authorization event from {identifier}')
        self.supvisors.fsm.on_authorization(identifier, authorized, master_identifier)

    def force_process_state(self, process: ProcessStatus, identifier: str, event_date: float,
                            forced_state: ProcessStates, reason: str) -> None:
        """ Publish the process state requested to all Supvisors instances.

        :param process: the process structure
        :param identifier: the identifier of the Supvisors instance where the process state is expected
        :param event_date: the date of the last process event received, used for the evaluation of the error
        :param forced_state: the process state to force if the expected state has not been received
        :param reason: the reason declared
        :return: None
        """
        # create payload from event
        payload = {'group': process.application_name, 'name': process.process_name,
                   'state': forced_state, 'forced': True,
                   'identifier': identifier,
                   'now': event_date, 'pid': 0, 'expected': False, 'spawnerr': reason,
                   'extra_args': process.extra_args}
        self.logger.debug(f'SupervisorListener.force_process_state: payload={payload}')
        self.publisher.send_process_state_event(payload)
