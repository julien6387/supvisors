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
import traceback
from http.client import CannotSendRequest, IncompleteRead
from threading import Event, Thread
from typing import Any, List

from supervisor.childutils import getRPCInterface
from supervisor.compat import xmlrpclib
from supervisor.xmlrpc import RPCError

from .internalinterface import InternalCommReceiver
from .ttypes import (DeferredRequestHeaders, InternalEventHeaders, RemoteCommEvents,
                     SupvisorsInstanceStates, SupvisorsStates, ISOLATION_STATES)
from .utils import SupervisorServerUrl


class SupvisorsMainLoop(Thread):
    """ Class for Supvisors main loop. All inputs are sequenced here.
    The Supervisor logger is not thread-safe so do NOT use it here.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - stop_event: the event used to stop the thread,
        - env: the environment variables linked to Supervisor security access,
        - proxy: the proxy to the internal RPC interface.
    """

    # to avoid a long list of exceptions in catches
    RpcExceptions = (KeyError, ValueError, OSError, ConnectionResetError,
                     CannotSendRequest, IncompleteRead, xmlrpclib.Fault, RPCError)

    # this will trigger the local periodic check
    WakeUpPeriod = 5.0

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure
        """
        # thread attributes
        Thread.__init__(self)
        # keep a reference to the Supvisors instance
        self.supvisors = supvisors
        # create stop event
        self.stop_event = Event()
        # create an XML-RPC client to the local Supervisor instance
        self.srv_url = SupervisorServerUrl(supvisors.supervisor_data.get_env())
        self.proxy = getRPCInterface(self.srv_url.env)

    @property
    def logger(self):
        return self.supvisors.logger

    @property
    def receiver(self) -> InternalCommReceiver:
        """ Get the Supvisors logger. """
        return self.supvisors.sockets.receiver

    @property
    def stopping(self) -> bool:
        """ Access to the loop attribute (used to drive tests on run method).

        :return: the condition to stop the main loop
        """
        return self.stop_event.is_set()

    def stop(self) -> None:
        """ Request to stop the infinite loop by resetting its flag.

        :return: None
        """
        if self.is_alive():
            self.stop_event.set()
            # the thread cannot be blocked in an XML-RPC call because of the close_httpservers called
            # just before this stop so join is expected to end properly
            self.join()

    def run(self) -> None:
        """ Contents of the infinite loop. """
        self.logger.info('SupvisorsMainLoop.run: entering main loop')
        # poll events forever
        while not self.stopping:
            # Test the sockets for any incoming message
            puller_event, external_events_sockets = self.receiver.poll()
            # test stop condition again: if Supervisor is stopping,
            # any XML-RPC call would block this thread and the other because of the join
            if not self.stopping:
                # process events
                try:
                    self.check_requests(puller_event)
                except:
                    self.logger.error('SupvisorsMainLoop.run: failed to check internal requests')
                    self.logger.error(f'SupvisorsMainLoop.run: {traceback.format_exc()}')
                try:
                    self.check_external_events(external_events_sockets)
                except:
                    self.logger.error('SupvisorsMainLoop.run: failed to check external events')
                    self.logger.error(f'SupvisorsMainLoop.run: {traceback.format_exc()}')
            # heartbeat management with publishers
            # TODO: check if it make sense in Multicast
            self.receiver.manage_heartbeat()
        self.receiver.close()
        self.logger.info('SupvisorsMainLoop.run: exiting main loop')

    def check_external_events(self, fds: List[int]) -> None:
        """ Forward external Supvisors events to the Supervisor main thread.

        :param fds: the list of socket descriptors to read from
        :return: None
        """
        for message in self.receiver.read_fds(fds):
            # a RemoteCommunicationEvent is used to push the event back into the Supervisor thread.
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_EVENT, message)

    def check_requests(self, puller_event: bool) -> None:
        """ Defer internal requests. """
        if puller_event:
            message = self.receiver.read_puller()
            if message:
                header, body = message
                deferred_request = DeferredRequestHeaders(header)
                # check publication event or deferred request
                if deferred_request == DeferredRequestHeaders.ISOLATE_INSTANCES:
                    # isolation request: disconnect the node from subscriber
                    self.receiver.disconnect_subscriber(body)
                else:
                    # XML-RPC request
                    self.send_request(deferred_request, body)

    def send_request(self, header: DeferredRequestHeaders, body) -> None:
        """ Perform the XML-RPC according to the header. """
        # first element of body is always the identifier of the destination Supvisors instance
        identifier = body[0]
        instance = self.supvisors.supvisors_mapper.instances[identifier]
        self.srv_url.update_url(instance.host_id, instance.http_port)
        # send message
        if header == DeferredRequestHeaders.CHECK_INSTANCE:
            self.check_instance(*body)
        elif header == DeferredRequestHeaders.START_PROCESS:
            self.start_process(*body)
        elif header == DeferredRequestHeaders.STOP_PROCESS:
            self.stop_process(*body)
        elif header == DeferredRequestHeaders.RESTART:
            self.restart(*body)
        elif header == DeferredRequestHeaders.SHUTDOWN:
            self.shutdown(*body)
        elif header == DeferredRequestHeaders.RESTART_SEQUENCE:
            self.restart_sequence(*body)
        elif header == DeferredRequestHeaders.RESTART_ALL:
            self.restart_all(*body)
        elif header == DeferredRequestHeaders.SHUTDOWN_ALL:
            self.shutdown_all(*body)

    def check_instance(self, identifier: str) -> None:
        """ Check isolation and get all process info asynchronously.

        :param identifier: the identifier of the Supvisors instance to get information from
        :return: None
        """
        authorized = None
        master_identifier = ''
        state_modes_payload = {'fsm_statecode': SupvisorsStates.OFF.value,
                               'discovery_mode': False,
                               'starting_jobs': False, 'stopping_jobs': False}
        all_info = []
        # get authorization from remote Supvisors instance
        try:
            supvisors_rpc = getRPCInterface(self.srv_url.env).supvisors
            # get remote perception of master node and state
            master_identifier = supvisors_rpc.get_master_identifier()
            self.logger.debug(f'SupvisorsMainLoop.check_instance: master_identifier={master_identifier}')
            # check authorization
            local_status_payload = supvisors_rpc.get_instance_info(self.supvisors.supvisors_mapper.local_identifier)
            self.logger.debug(f'SupvisorsMainLoop.check_instance: master_identifier={master_identifier}')
            # check how the remote Supvisors instance defines itself
            remote_status_payload = supvisors_rpc.get_instance_info(identifier)
            self.logger.debug(f'SupvisorsMainLoop.check_instance: master_identifier={master_identifier}')
            state_modes_payload = {key: remote_status_payload[key] for key in state_modes_payload}
        except SupvisorsMainLoop.RpcExceptions:
            # Remote Supvisors instance closed in the gap or Supvisors is incorrectly configured
            self.logger.error(f'SupvisorsMainLoop.check_instance: failed to check Supvisors={identifier}')
        else:
            instance_state = SupvisorsInstanceStates(local_status_payload['statecode'])
            # authorization is granted if the remote Supvisors instances did not isolate the local Supvisors instance
            authorized = instance_state not in ISOLATION_STATES
        # get process info if authorized and remote not restarting or shutting down
        if authorized:
            try:
                # get information about all processes handled by Supervisor
                all_info = supvisors_rpc.get_all_local_process_info()
            except SupvisorsMainLoop.RpcExceptions:
                self.logger.error('SupvisorsMainLoop.check_instance: failed to get process information'
                                  f' from Supvisors={identifier}')
                # the remote Supvisors instance may have gone to a closing state since the previous calls and thus be
                # not able to respond to the request (long shot but not impossible)
                # do NOT set authorized to False in this case or an unwanted isolation may happen
        # inform local Supvisors that authorization is available
        message = identifier, authorized, master_identifier
        self.logger.info(f'SupvisorsMainLoop.check_instance: identifier={identifier} authorized={authorized}'
                         f' master_identifier={master_identifier}')
        self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH, message)
        # provide the local Supvisors with the remote Supvisors instance state and modes
        instance = self.supvisors.supvisors_mapper.instances[identifier]
        origin = instance.ip_address, instance.http_port
        message = InternalEventHeaders.STATE.value, (identifier, state_modes_payload)
        self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_EVENT, (origin, message))
        # inform local Supvisors about the processes available remotely
        if all_info:
            message = identifier, all_info
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_INFO, message)

    def start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.start_args(namespec, extra_args, False)
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error(f'SupvisorsMainLoop.start_process: failed to start process {namespec} on {identifier}'
                              f' with extra_args="{extra_args}"')

    def stop_process(self, identifier: str, namespec: str) -> None:
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.stopProcess(namespec, False)
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error(f'SupvisorsMainLoop.stop_process: failed to stop process {namespec} on {identifier}')

    def restart(self, identifier: str) -> None:
        """ Restart a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.restart()
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error(f'SupvisorsMainLoop.restart: failed to restart node {identifier}')

    def shutdown(self, identifier: str) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.shutdown()
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error(f'SupvisorsMainLoop.shutdown: failed to shutdown node {identifier}')

    def restart_sequence(self, identifier: str) -> None:
        """ Ask the Supvisors Master to trigger the DEPLOYMENT phase. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.restart_sequence()
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error('SupvisorsMainLoop.restart_sequence: failed to send Supvisors restart_sequence'
                              f' to Master {identifier}')

    def restart_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.restart()
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error('SupvisorsMainLoop.restart_all: failed to send Supvisors restart'
                              f' to Master {identifier}')

    def shutdown_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to shut down Supvisors. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.shutdown()
        except SupvisorsMainLoop.RpcExceptions:
            self.logger.error('SupvisorsMainLoop.shutdown_all: failed to send Supvisors shutdown'
                              f' to Master {identifier}')

    def send_remote_comm_event(self, event_type: RemoteCommEvents, event_data) -> None:
        """ Shortcut for the use of sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(event_type.value, json.dumps(event_data))
        except SupvisorsMainLoop.RpcExceptions:
            # expected on restart / shutdown
            self.logger.error('SupvisorsMainLoop.send_remote_comm_event: failed to send event to Supervisor'
                              f' {event_type} - {event_data}')
