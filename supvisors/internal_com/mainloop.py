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

import asyncio
import json
import queue
import threading
import traceback
from http.client import CannotSendRequest, IncompleteRead
from typing import Any, Optional

from supervisor.childutils import getRPCInterface
from supervisor.compat import xmlrpclib
from supervisor.loggers import Logger
from supervisor.xmlrpc import RPCError

from supvisors.ttypes import InternalEventHeaders, SupvisorsInstanceStates, Ipv4Address, SUPVISORS, ISOLATION_STATES
from supvisors.utils import SupervisorServerUrl
from .internal_com import SupvisorsInternalReceiver
from .internalinterface import ASYNC_TIMEOUT
from .pushpull import DeferredRequestHeaders


class SupervisorProxy(threading.Thread):
    """ xmlrpclib.ServerProxy is not thread-safe so all requests are pushed to a synchronous queue
    so that the requests are served and the async loop is not blocked. """

    QUEUE_TIMEOUT = 1.0

    # List of keys useful to build a SupvisorsState event
    StateModesKeys = ['fsm_statecode', 'discovery_mode', 'master_identifier', 'starting_jobs', 'stopping_jobs']

    # to avoid a long list of exceptions in catches
    RpcExceptions = (KeyError, ValueError, OSError, ConnectionResetError,
                     CannotSendRequest, IncompleteRead, xmlrpclib.Fault, RPCError)

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        threading.Thread.__init__(self, daemon=True)
        self.supvisors = supvisors
        self.queue: queue.Queue = queue.Queue()
        self.event: threading.Event = threading.Event()
        # SupervisorServerUrl contains the environment variables linked to Supervisor security access,
        self.srv_url: SupervisorServerUrl = SupervisorServerUrl(supvisors.supervisor_data.get_env())
        # create an XML-RPC client to the local Supervisor instance
        self.proxy = getRPCInterface(self.srv_url.env)

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    def push_event(self, message):
        """ Add an event to send to Supervisor. """
        self.queue.put_nowait((None, message))

    def push_request(self, request: DeferredRequestHeaders, params):
        """ Add an event to send to Supervisor. """
        self.queue.put_nowait((request, params))

    def stop(self):
        """ Set the event to stop the main loop. """
        self.event.set()

    def run(self):
        """ Main loop. """
        self.logger.info('SupervisorProxy.run: entering main loop')
        while not self.event.is_set():
            try:
                event_type, event_data = self.queue.get(timeout=SupervisorProxy.QUEUE_TIMEOUT)
            except queue.Empty:
                self.logger.blather('SupervisorProxy.run: nothing received')
            else:
                if event_type is not None:
                    self.execute(event_type, event_data)
                else:
                    self.send_remote_comm_event(event_data)
        self.logger.info('SupervisorProxy.run: exiting main loop')

    def execute(self, header: DeferredRequestHeaders, body) -> None:
        """ Perform the XML-RPC according to the header. """
        # first element of body is always the identifier of the destination Supvisors instance
        identifier = body[0]
        instance = self.supvisors.mapper.instances[identifier]
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
        """ Check isolation and get all process info.

        :param identifier: the identifier of the Supvisors instance to get information from.
        :return: None.
        """
        authorized = self._is_authorized(identifier)
        self.logger.info(f'SupervisorProxy.check_instance: identifier={identifier} authorized={authorized}')
        if authorized:
            self._transfer_states_modes(identifier)
            self._transfer_process_info(identifier)
        # inform local Supvisors that authorization result is available
        message = InternalEventHeaders.AUTHORIZATION.value, (identifier, authorized)
        self.send_remote_comm_event((self._get_origin(identifier), message))

    def _get_origin(self, identifier: str) -> Ipv4Address:
        """ Return the IPv4 tuple associated with the Supvisors instance. """
        instance = self.supvisors.mapper.instances[identifier]
        return instance.ip_address, instance.http_port

    def _is_authorized(self, identifier: str) -> Optional[bool]:
        """ Get authorization from remote Supvisors instance.
        If the remote Supvisors instance considers the local Supvisors instance as ISOLATED, authorization is denied.

        :param identifier: the identifier of the remote Supvisors instance.
        :return: True if the local Supvisors instance is accepted by the remote Supvisors instance.
        """
        try:
            supvisors_rpc = getRPCInterface(self.srv_url.env).supvisors
            # check authorization
            local_status_payload = supvisors_rpc.get_instance_info(self.supvisors.context.local_identifier)
            self.logger.debug(f'SupervisorProxy._is_authorized: local_status_payload={local_status_payload}')
        except SupervisorProxy.RpcExceptions:
            # Remote Supvisors instance closed in the gap or Supvisors is incorrectly configured
            self.logger.error(f'SupervisorProxy._is_authorized: failed to check Supvisors={identifier}')
            return None
        # check the local Supvisors instance state as seen by the remote Supvisors instance
        state = local_status_payload['statecode']
        try:
            instance_state = SupvisorsInstanceStates(state)
        except ValueError:
            self.logger.error(f'SupervisorProxy._is_authorized: unknown Supvisors instance state={state}')
            return False
        # authorization is granted if the remote Supvisors instances did not isolate the local Supvisors instance
        return instance_state not in ISOLATION_STATES

    def _transfer_process_info(self, identifier: str) -> None:
        """ Get the process information from the remote Supvisors instance and post it to the local Supvisors instance.

        :param identifier: the identifier of the remote Supvisors instance.
        :return: None
        """
        # get information about all processes handled by Supervisor
        try:
            supvisors_rpc = getRPCInterface(self.srv_url.env).supvisors
            all_info = supvisors_rpc.get_all_local_process_info()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy._transfer_process_info: failed to get process information'
                              f' from Supvisors={identifier}')
            # the remote Supvisors instance may have gone to a closing state since the previous calls and thus be
            # not able to respond to the request (long shot but not impossible)
            # do NOT set authorized to False in this case or an unwanted isolation may happen
        else:
            # inform local Supvisors about the processes available remotely
            message = InternalEventHeaders.ALL_INFO.value, (identifier, all_info)
            self.send_remote_comm_event((self._get_origin(identifier), message))

    def _transfer_states_modes(self, identifier: str) -> None:
        """ Get the states and modes from the remote Supvisors instance and post it to the local Supvisors instance.

        :param identifier: the identifier of the remote Supvisors instance.
        :return: None
        """
        # get authorization from remote Supvisors instance
        try:
            # check how the remote Supvisors instance defines itself
            supvisors_rpc = getRPCInterface(self.srv_url.env).supvisors
            remote_status = supvisors_rpc.get_instance_info(identifier)
        except SupervisorProxy.RpcExceptions:
            # Remote Supvisors instance closed in the gap or Supvisors is incorrectly configured
            self.logger.error(f'SupervisorProxy._transfer_states_modes: failed to check Supvisors={identifier}')
        else:
            self.logger.debug(f'SupervisorProxy._transfer_states_modes: remote_status={remote_status}')
            state_modes = {key: remote_status[key] for key in SupervisorProxy.StateModesKeys}
            # provide the local Supvisors with the remote Supvisors instance state and modes
            message = InternalEventHeaders.STATE.value, (identifier, state_modes)
            self.send_remote_comm_event((self._get_origin(identifier), message))

    def start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.start_args(namespec, extra_args, False)
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.start_process: failed to start process {namespec} on {identifier}'
                              f' with extra_args="{extra_args}"')

    def stop_process(self, identifier: str, namespec: str) -> None:
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.stopProcess(namespec, False)
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.stop_process: failed to stop process {namespec} on {identifier}')

    def restart(self, identifier: str) -> None:
        """ Restart a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.restart()
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.restart: failed to restart node {identifier}')

    def shutdown(self, identifier: str) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.shutdown()
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.shutdown: failed to shutdown node {identifier}')

    def restart_sequence(self, identifier: str) -> None:
        """ Ask the Supvisors Master to trigger the DEPLOYMENT phase. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.restart_sequence()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.restart_sequence: failed to send Supvisors restart_sequence'
                              f' to Master {identifier}')

    def restart_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.restart()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.restart_all: failed to send Supvisors restart'
                              f' to Master {identifier}')

    def shutdown_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to shut down Supvisors. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.shutdown()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.shutdown_all: failed to send Supvisors shutdown'
                              f' to Master {identifier}')

    def send_remote_comm_event(self, event_data) -> None:
        """ Perform the Supervisor sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(SUPVISORS, json.dumps(event_data))
        except SupervisorProxy.RpcExceptions:
            # expected on restart / shutdown
            self.logger.error(f'SupervisorProxy.send_remote_comm_event: failed to send to Supervisor {event_data}')
            self.logger.debug(f'SupervisorProxy.send_remote_comm_event: {traceback.format_exc()}')


class SupvisorsMainLoop(threading.Thread):
    """ Class for Supvisors main loop. All inputs are sequenced here.
    The Supervisor logger is not thread-safe so do NOT use it here.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - async_loop: the asynchronous event loop that will run in the thread,
        - receiver: the asynchronous tasks that will run in the thread,
        - proxy: the proxy to the internal RPC interface.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure
        """
        # thread attributes
        threading.Thread.__init__(self, daemon=True)
        # keep a reference to the Supvisors instance
        self.supvisors = supvisors
        # the asyncio object that will receive all events
        self.receiver: Optional[SupvisorsInternalReceiver] = None
        # create an XML-RPC client to the local Supervisor instance
        self.proxy: SupervisorProxy = SupervisorProxy(supvisors)

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    def stop(self) -> None:
        """ Request to stop the infinite loop by resetting its flag.
        This is meant to be called from the Supervisor thread.

        :return: None
        """
        if self.is_alive():
            self.receiver.stop()
            # the thread cannot be blocked in an XML-RPC call because of the close_httpservers called
            # just before this stop so join is expected to end properly
            self.join()

    def run(self):
        """ The SupvisorsMainLoop thread runs an asynchronous event loop for all I/O operations. """
        self.logger.info('SupvisorsMainLoop.run: entering main loop')
        self.proxy.start()
        # assign a new asynchronous event loop to this thread
        async_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(async_loop)
        # create the asyncio object that will receive all events
        self.receiver = SupvisorsInternalReceiver(async_loop, self.supvisors)
        # get the receiver tasks
        all_coro = self.receiver.get_tasks()
        # add the reception tasks for this class
        all_coro.extend([self.read_queue(self.receiver.subscriber_queue, self.check_remote_event),
                         self.read_queue(self.receiver.requester_queue, self.check_requests),
                         self.read_queue(self.receiver.discovery_queue, self.check_discovery_event)])
        all_tasks = asyncio.gather(*all_coro)
        # run the asynchronous event loop with the given tasks
        async_loop.run_until_complete(all_tasks)
        # exiting the main loop
        self.logger.debug('SupvisorsMainLoop.run: out of async loop')
        self.proxy.stop()
        self.proxy.join()
        self.logger.info('SupvisorsMainLoop.run: exiting main loop')

    async def read_queue(self, async_queue: asyncio.Queue, callback):
        """ Handle the messages received from the subscribers.
        It uses the same event as the receiver tasks to stop.
        """
        while not self.receiver.stop_event.is_set():
            try:
                message = await asyncio.wait_for(async_queue.get(), ASYNC_TIMEOUT)
            except asyncio.TimeoutError:
                # no message
                self.logger.blather('SupvisorsMainLoop.read_queue: nothing received')
            else:
                await callback(message)

    async def check_remote_event(self, message):
        """ Transfer the message to the Supervisor thread. """
        self.logger.trace(f'SupvisorsMainLoop.check_remote_event: message={message}')
        self.proxy.push_event(message)

    async def check_discovery_event(self, message):
        """ Transfer the message to the Supervisor thread. """
        self.logger.trace(f'SupvisorsMainLoop.check_discovery_event: message={message}')
        self.proxy.push_event(message)

    async def check_requests(self, message) -> None:
        """ Defer internal requests. """
        header, body = message
        self.logger.debug(f'SupvisorsMainLoop.check_requests: header={header} body={body}')
        deferred_request = DeferredRequestHeaders(header)
        # check publication event or deferred request
        if deferred_request == DeferredRequestHeaders.ISOLATE_INSTANCES:
            # isolation request: disconnect the Supvisors instances from the subscribers
            self.receiver.subscribers.disconnect_subscribers(body)
        elif deferred_request == DeferredRequestHeaders.CONNECT_INSTANCE:
            # discovery mode: a new Supvisors instance has to be added to the subscribers
            for identifier in body:
                self.logger.info(f'SupvisorsMainLoop.check_requests: add subscriber to {identifier}')
                coro = self.receiver.subscribers.create_coroutine(identifier)
                if coro:
                    self.receiver.loop.create_task(coro)
        else:
            # XML-RPC requests
            self.proxy.push_request(deferred_request, body)
