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
import traceback
from typing import Any, Optional, Union

from supervisor import events
from supervisor.loggers import Logger
from supervisor.options import make_namespec
from supervisor.states import ProcessStates, _process_states_by_code
from supervisor.xmlrpc import RPCError

from .external_com import create_external_publisher, EventPublisherInterface
from .instancestatus import SupvisorsInstanceStatus
from .internal_com.mapper import SupvisorsInstanceId
from .internal_com.multicast import SupvisorsDiscovery, MulticastSender
from .internal_com.rpchandler import RpcHandler
from .process import ProcessStatus
from .statemachine import FiniteStateMachine
from .statscompiler import HostStatisticsCompiler, ProcStatisticsCompiler
from .ttypes import (ProcessEvent, ProcessAddedEvent, ProcessRemovedEvent, ProcessEnabledEvent, ProcessDisabledEvent,
                     SUPVISORS_PUBLICATION, SUPVISORS_NOTIFICATION, PublicationHeaders, NotificationHeaders, Payload)

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


class SupervisorListener:
    """ This class subscribes directly to the internal Supervisor events.
    These events are published to all Supvisors instances.

    Attributes are:
        - supvisors: the Supvisors global structure ;
        - counter: the TICK sequence counter.
    """

    supvisors: Any = None
    counter: int = 0

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # NOTE: The SupvisorsMainLoop cannot be created at this level
        #       Before running, Supervisor forks when daemonized and the sockets are then lost
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

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    @property
    def local_instance(self) -> SupvisorsInstanceId:
        """ Get the local Supvisors instance id. """
        return self.supvisors.mapper.local_instance

    @property
    def local_status(self) -> SupvisorsInstanceStatus:
        """ Get the local Supvisors instance status. """
        return self.supvisors.context.local_status

    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors identifier. """
        return self.local_instance.identifier

    @property
    def stats_collector(self) -> Any:
        """ Get the Supvisors object in charge of collecting host and process statistics.
        NOTE: May be None if psutil is not installed. """
        return self.supvisors.stats_collector

    @property
    def host_compiler(self) -> Optional[HostStatisticsCompiler]:
        """ Get the Supvisors function in charge of compiling host statistics. """
        return self.supvisors.host_compiler

    @property
    def process_compiler(self) -> Optional[ProcStatisticsCompiler]:
        """ Get the Supvisors instance in charge of compiling process statistics. """
        return self.supvisors.process_compiler

    @property
    def fsm(self) -> FiniteStateMachine:
        """ Get the Supvisors state machine. """
        return self.supvisors.fsm

    @property
    def rpc_handler(self) -> RpcHandler:
        """ Get the com interface used to publish Supvisors internal events to all Supvisors instances. """
        return self.supvisors.rpc_handler

    @property
    def mc_sender(self) -> Optional[MulticastSender]:
        """ Get the com interface used to publish Supvisors internal events to all Supvisors instances. """
        if self.supvisors.discovery_handler:
            return self.supvisors.discovery_handler.mc_sender
        return None

    @property
    def external_publisher(self) -> Optional[EventPublisherInterface]:
        """ Get the com interface used to publish Supvisors events to all Supvisors listeners. """
        return self.supvisors.external_publisher

    def on_running(self, _):
        """ Called when Supervisor is RUNNING.
        This method starts the Supvisors main loop. """
        self.logger.info('SupervisorListener.on_running: local supervisord is RUNNING')
        try:
            # reset the tick counter
            self.counter = 0
            # update Supervisor internal data for Supvisors support
            self.supvisors.supervisor_updater.on_supervisor_start()
            # WARN: Start the statistics collector first to avoid forking while other threads are running.
            #       One of them might use stdout or stderr at fork time and a lock could be held forever,
            #       leading Supvisors to hang at stop time
            if self.stats_collector:
                self.stats_collector.start()
            # NOTE: The communication structures cannot be created before this level
            #       Before running, Supervisor forks when daemonized and the sockets are then lost
            #       At this point, Supervisor has forked if not daemonized
            self.supvisors.rpc_handler = RpcHandler(self.supvisors)
            if self.supvisors.options.discovery_mode:
                self.supvisors.discovery_handler = SupvisorsDiscovery(self.supvisors)
            self.supvisors.external_publisher = create_external_publisher(self.supvisors)
            # Trigger the FSM
            self.fsm.next()
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_running: {traceback.format_exc()}')

    def on_stopping(self, _):
        """ Called when Supervisor is STOPPING.
        This method stops the Supvisors main loop. """
        self.logger.warn('SupervisorListener.on_stopping: local supervisord is STOPPING')
        try:
            # Stop the process statistics collector
            if self.stats_collector:
                self.stats_collector.stop()
            # force Supervisor to close HTTP servers
            # this will prevent any pending XML-RPC request to block the Supervisor proxies
            self.supvisors.supervisor_data.close_httpservers()
            # close RPC handler threads
            self.logger.debug('SupervisorListener.on_stopping: closing Supervisor proxies...')
            self.supvisors.rpc_handler.stop()
            self.logger.debug('SupervisorListener.on_stopping: Supervisor proxies closed')
            # close discovery handler thread
            if self.supvisors.discovery_handler:
                self.logger.debug('SupervisorListener.on_stopping: closing Supvisors discovery...')
                self.supvisors.discovery_handler.stop()
                self.logger.debug('SupervisorListener.on_stopping: Supvisors discovery closed')
            # close external publication thread
            if self.external_publisher:
                self.logger.debug('SupervisorListener.on_stopping: stopping external publisher...')
                self.external_publisher.close()
                self.logger.debug('SupervisorListener.on_stopping: external publisher stopped')
            # unsubscribe from events
            events.clear()
            # finally, close logger
            # WARN: only if it is not the supervisor logger
            if hasattr(self.logger, 'SUPVISORS'):
                self.logger.close()
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_stopping: {traceback.format_exc()}')

    def on_tick(self, event: events.TickEvent) -> None:
        """ Called when a TickEvent is notified.
        The event is published to all Supvisors instances.
        Then statistics are published and periodic task is triggered.

        :param event: the Supervisor TICK event.
        :return: None.
        """
        try:
            self.logger.debug(f'SupervisorListener.on_tick: got TickEvent from Supervisor {event}')
            # add the monotonic time information for more resolution and robustness
            payload = {'when': event.when,
                       'when_monotonic': time.monotonic(),
                       'sequence_counter': self.counter}
            payload.update(self.local_instance.serial())
            self.counter += 1
            self.logger.trace(f'SupervisorListener.on_tick: payload={payload}')
            # trigger the periodic check
            # NOTE: do not involve the Supvisors internal communications to that end
            #       because it is used to detect network failures
            self.supvisors.context.on_local_tick_event(payload)
            self.fsm.on_timer_event(payload)
            # publish the TICK to all Supvisors instances
            self.rpc_handler.send_tick_event(payload)
            if self.mc_sender:
                self.mc_sender.send_discovery_event(payload)
            # handle the statistics collection
            self._on_tick_stats()
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_tick: {traceback.format_exc()}')

    def _on_tick_stats(self) -> None:
        """ Publish the host and process statistics collected since the latest tick. """
        if self.stats_collector:
            self.stats_collector.alive()
            # get and publish the host statistics collected from the last tick
            for stats in self.stats_collector.get_host_stats():
                # send to local host compiler
                self.on_host_statistics(self.local_identifier, stats)
                # publish host statistics to other Supvisors instances
                self.rpc_handler.send_host_statistics(stats)
            # get and publish the process statistics collected from the last tick
            for stats in self.stats_collector.get_process_stats():
                # send to local process compiler
                self.on_process_statistics(self.local_identifier, stats)
                # publish host statistics to other Supvisors instances
                self.rpc_handler.send_process_statistics(stats)

    def on_process_state(self, event: events.ProcessStateEvent) -> None:
        """ Called when a ProcessStateEvent is sent by the local Supervisor.
        The event is published to all Supvisors instances. """
        try:
            event_name = events.getEventNameByType(event.__class__)
            namespec = make_namespec(event.process.group.config.name, event.process.config.name)
            self.logger.debug(f'SupervisorListener.on_process_state: got {event_name} for {namespec}')
            process_state: ProcessStates = _process_states_by_name[event_name.split('_')[-1]]
            # create payload from event
            payload = {'identifier': self.local_identifier,
                       'nick_identifier': self.local_instance.nick_identifier,
                       'name': event.process.config.name,
                       'group': event.process.group.config.name,
                       'state': process_state,
                       'now': time.time(),
                       'now_monotonic': time.monotonic(),
                       'pid': event.process.pid,
                       'expected': event.expected,
                       'spawnerr': event.process.spawnerr or '',
                       'extra_args': event.process.extra_args,
                       'disabled': event.process.supvisors_config.program_config.disabled}
            self.logger.trace(f'SupervisorListener.on_process_state: payload={payload}')
            # update local Supvisors instance
            self.fsm.on_process_state_event(self.local_status, payload)
            # publish to the other Supvisors instances
            self.rpc_handler.send_process_state_event(payload)
            # post-event actions: check obsolete processes and update internal monotonic times
            if process_state == ProcessStates.STARTING:
                self.supvisors.supervisor_data.update_start(namespec)
            elif process_state in [ProcessStates.STOPPED, ProcessStates.BACKOFF, ProcessStates.EXITED]:
                self.supvisors.supervisor_data.update_stop(namespec)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_state: {traceback.format_exc()}')

    def _get_local_process_info(self, namespec: str) -> Payload:
        """ Use the Supvisors RPCInterface to get local information on this process.

        :param namespec: the process namespec
        :return: the process local information
        """
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
                # update local Supvisors instance
                self.fsm.on_process_added_event(self.local_status, process_info)
                # publish to the other Supvisors instances
                self.rpc_handler.send_process_added_event(process_info)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_added: {traceback.format_exc()}')

    def on_process_removed(self, event: ProcessRemovedEvent) -> None:
        """ Called when a process has been removed due to a numprocs change.

        :param event: the ProcessRemovedEvent object.
        :return: None.
        """
        try:
            namespec = make_namespec(event.process.group.config.name, event.process.config.name)
            self.logger.debug(f'SupervisorListener.on_process_removed: got ProcessRemovedEvent for {namespec}')
            payload = {'name': event.process.config.name, 'group': event.process.group.config.name}
            self.logger.trace(f'SupervisorListener.on_process_removed: payload={payload}')
            # update local Supvisors instance
            self.fsm.on_process_removed_event(self.local_status, payload)
            # publish to the other Supvisors instances
            self.rpc_handler.send_process_removed_event(payload)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_removed: {traceback.format_exc()}')

    def on_process_disability(self, event: Union[ProcessEnabledEvent, ProcessDisabledEvent]) -> None:
        """ Called when a process has been enabled or disabled.

        :param event: the ProcessEnabledEvent or ProcessDisabledEvent object.
        :return: None.
        """
        try:
            namespec = make_namespec(event.process.group.config.name, event.process.config.name)
            self.logger.debug('SupervisorListener.on_process_disability: got ProcessEnabledEvent or'
                              f' ProcessDisabledEvent for {namespec}')
            # use RPCInterface to get local information on this process
            process_info = self._get_local_process_info(namespec)
            if process_info:
                self.logger.trace(f'SupervisorListener.on_process_disability: process_info={process_info}')
                # update local Supvisors instance
                self.fsm.on_process_disability_event(self.local_status, process_info)
                # publish to the other Supvisors instances
                self.rpc_handler.send_process_disability_event(process_info)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_process_disability: {traceback.format_exc()}')

    def on_group_added(self, event: events.ProcessGroupAddedEvent) -> None:
        """ Called when a group has been added following a Supervisor configuration update.
        This method performs an update of the internal data structure and sends a process payload
        to all other Supvisors instances.

        :param event: the ProcessGroupAddedEvent object.
        :return: None.
        """
        try:
            self.logger.debug(f'SupervisorListener.on_group_added: group={event.group}')
            # update Supervisor internal data for extra_args
            self.supvisors.supervisor_updater.on_group_added(event.group)
            # inform all Supvisors instances that new processes have been added
            for process_name in self.supvisors.supervisor_data.get_group_processes(event.group):
                namespec = make_namespec(event.group, process_name)
                # use RPCInterface to get local information on this process
                process_info = self._get_local_process_info(namespec)
                if process_info:
                    self.logger.trace(f'SupervisorListener.on_process_added: process_info={process_info}')
                    # update local Supvisors instance
                    self.fsm.on_process_added_event(self.local_status, process_info)
                    # publish to the other Supvisors instances
                    self.rpc_handler.send_process_added_event(process_info)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_group_added: {traceback.format_exc()}')

    def on_group_removed(self, event: events.ProcessGroupRemovedEvent) -> None:
        """ Called when a group has been removed following a Supervisor configuration update.
        Unlike the ProcessGroupAddedEvent case, Supervisor does not send anything else so other Supvisors instances
        must be informed.

        :param event: the ProcessGroupRemovedEvent object.
        :return: None.
        """
        try:
            # reuse existing event for process removed event
            self.logger.debug(f'SupervisorListener.on_group_removed: group={event.group}')
            payload = {'name': '*', 'group': event.group}
            self.logger.trace(f'SupervisorListener.on_process_removed: payload={payload}')
            # update local Supvisors instance
            self.fsm.on_process_removed_event(self.local_status, payload)
            # publish to the other Supvisors instances
            self.rpc_handler.send_process_removed_event(payload)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_group_removed: {traceback.format_exc()}')

    def on_remote_event(self, event: events.RemoteCommunicationEvent) -> None:
        """ Called when a RemoteCommunicationEvent is notified.
        This is used to sequence the events received from the Supvisors thread with the other events handled
        by the local Supervisor. """
        self.logger.trace(f'SupervisorListener.on_remote_event: type={event.type} data={event.data}')
        try:
            if event.type == SUPVISORS_PUBLICATION:
                self.read_publication(event.data)
            elif event.type == SUPVISORS_NOTIFICATION:
                self.read_notification(event.data)
        except Exception:
            # Supvisors shall never endanger the Supervisor thread
            self.logger.critical(f'SupervisorListener.on_remote_event: {traceback.format_exc()}')

    def read_notification(self, message: str):
        """ Read and process a notification from the Supervisor event queue. """
        event_origin, (event_type, event_data) = json.loads(message)
        header = NotificationHeaders(event_type)
        # NOTE: DISCOVERY messages contain the necessary information for Supvisors instances discovery,
        #       so it has to be processed first
        if header == NotificationHeaders.DISCOVERY:
            self.logger.trace(f'SupervisorListener.read_notification: DISCOVERY from {event_origin}')
            self.fsm.on_discovery_event(event_origin)
            return
        # check message origin validity
        status: SupvisorsInstanceStatus = self.supvisors.context.is_valid(*event_origin)
        if not status:
            self.logger.debug(f'SupervisorListener.read_notification: event from unknown Supvisors={event_origin}')
            return
        # process the message depending on the event type
        if header == NotificationHeaders.AUTHORIZATION:
            self.logger.trace(f'SupervisorListener.read_notification: AUTHORIZATION from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_authorization(status, event_data)
        elif header == NotificationHeaders.STATE:
            self.logger.trace(f'SupervisorListener.read_notification: STATE from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_state_event(status, event_data)
        elif header == NotificationHeaders.ALL_INFO:
            self.logger.trace(f'SupervisorListener.read_notification: ALL_INFO from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_all_process_info(status, event_data)
        elif header == NotificationHeaders.INSTANCE_FAILURE:
            self.logger.trace(f'SupervisorListener.read_notification: INSTANCE_FAILURE from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_instance_failure(status)

    def read_publication(self, message: str):
        """ Read and process a notification from the Supervisor event queue. """
        event_origin, (event_type, event_data) = json.loads(message)
        event_identifier = event_origin[0]
        header = PublicationHeaders(event_type)
        # check message origin validity
        status: SupvisorsInstanceStatus = self.supvisors.context.is_valid(*event_origin)
        if not status:
            self.logger.error(f'SupervisorListener.read_publication: event from unknown Supvisors={event_origin}')
            return
        # process the message depending on the event type
        if header == PublicationHeaders.TICK:
            self.logger.trace(f'SupervisorListener.read_publication: TICK from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_tick_event(status, event_data)
        elif header == PublicationHeaders.PROCESS:
            self.logger.trace(f'SupervisorListener.read_publication: PROCESS from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_process_state_event(status, event_data)
        elif header == PublicationHeaders.PROCESS_ADDED:
            self.logger.trace(f'SupervisorListener.read_publication: PROCESS_ADDED from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_process_added_event(status, event_data)
        elif header == PublicationHeaders.PROCESS_REMOVED:
            self.logger.trace(f'SupervisorListener.read_publication: PROCESS_REMOVED from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_process_removed_event(status, event_data)
        elif header == PublicationHeaders.PROCESS_DISABILITY:
            self.logger.trace(f'SupervisorListener.read_publication: PROCESS_DISABILITY from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_process_disability_event(status, event_data)
        elif header == PublicationHeaders.HOST_STATISTICS:
            # this Supvisors could handle statistics even if psutil is not installed
            self.logger.trace(f'SupervisorListener.read_publication: HOST_STATISTICS from {status.usage_identifier}:'
                              f' {event_data}')
            self.on_host_statistics(event_identifier, event_data)
        elif header == PublicationHeaders.PROCESS_STATISTICS:
            # this Supvisors could handle statistics even if psutil is not installed
            self.logger.trace(f'SupervisorListener.read_publication: PROCESS_STATISTICS from {status.usage_identifier}:'
                              f' {event_data}')
            self.on_process_statistics(event_identifier, event_data)
        elif header == PublicationHeaders.STATE:
            self.logger.trace(f'SupervisorListener.read_publication: STATE from {status.usage_identifier}:'
                              f' {event_data}')
            self.fsm.on_state_event(status, event_data)

    def on_host_statistics(self, identifier: str, event_data: Payload) -> None:
        """ Compile the host statistics received from the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent host statistics.
        :param event_data: the latest host statistics from the Supvisors instance.
        :return: None.
        """
        integrated_stats_list = self.host_compiler.push_statistics(identifier, event_data)
        if integrated_stats_list and self.external_publisher:
            for integrated_stats in integrated_stats_list:
                self.external_publisher.send_host_statistics(integrated_stats)

    def on_process_statistics(self, identifier: str, event_data: Payload):
        """ Compile the process statistics received from the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance that sent process statistics.
        :param event_data: the latest process statistics from the Supvisors instance.
        :return: None.
        """
        integrated_stats_list = self.process_compiler.push_statistics(identifier, event_data)
        if integrated_stats_list and self.external_publisher:
            for integrated_stats in integrated_stats_list:
                self.external_publisher.send_process_statistics(integrated_stats)

    def force_process_state(self, process: ProcessStatus, identifier: str,
                            event_time: float,
                            forced_state: ProcessStates, reason: str) -> None:
        """ Publish the process state requested to all Supvisors instances.

        :param process: the process structure.
        :param identifier: the identifier of the Supvisors instance where the process state is expected.
        :param event_time: the monotonic time of the last process event received, used for the evaluation of the error.
        :param forced_state: the process state to force if the expected state has not been received.
        :param reason: the reason declared.
        :return: None.
        """
        nick_identifier = ''
        if identifier:
            nick_identifier = self.supvisors.mapper.instances[identifier].nick_identifier
        # create payload from event
        payload = {'identifier': identifier, 'nick_identifier': nick_identifier,
                   'group': process.application_name, 'name': process.process_name,
                   'state': forced_state, 'forced': True,
                   'now': time.time(), 'now_monotonic': event_time,
                   'pid': 0, 'expected': False, 'spawnerr': reason,
                   'extra_args': process.extra_args}
        self.logger.debug(f'SupervisorListener.force_process_state: payload={payload}')
        # update local Supvisors instance
        self.fsm.on_process_state_event(self.local_status, payload)
        # publish to the other Supvisors instances
        self.rpc_handler.send_process_state_event(payload)
