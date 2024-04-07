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
from typing import Any, Optional, Tuple

from supervisor.childutils import getRPCInterface
from supervisor.compat import xmlrpclib
from supervisor.loggers import Logger
from supervisor.xmlrpc import RPCError

from supvisors.ttypes import (Ipv4Address, InternalEventHeaders, RequestHeaders, PublicationHeaders,
                              SupvisorsInstanceStates, SUPVISORS)
from supvisors.utils import SupervisorServerUrl
from .internal_com import SupvisorsInternalReceiver
from .internalinterface import ASYNC_TIMEOUT


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
        self.proxies = {self.local_identifier: getRPCInterface(self.srv_url.env)}

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.supvisors.mapper.local_identifier

    def push_message(self, *message):
        """ Add an event to send to Supervisor. """
        self.queue.put_nowait(message)

    def stop(self):
        """ Set the event to stop the main loop. """
        self.event.set()

    def run(self):
        """ Main loop. """
        self.logger.info('SupervisorProxy.run: entering main loop')
        while not self.event.is_set():
            try:
                event_type, event_body = self.queue.get(timeout=SupervisorProxy.QUEUE_TIMEOUT)
            except queue.Empty:
                self.logger.blather('SupervisorProxy.run: nothing received')
            else:
                if event_type == InternalEventHeaders.REQUEST:
                    self.execute(event_body)
                elif event_type == InternalEventHeaders.PUBLICATION:
                    self.publish(event_body)
                elif event_type == InternalEventHeaders.DISCOVERY:
                    self.send_remote_comm_event(self.local_identifier, event_body)
        self.logger.info('SupervisorProxy.run: exiting main loop')

    def _get_origin(self, identifier: str) -> Tuple[str, Ipv4Address]:
        """ Return the identification of the Supvisors instance. """
        return self.supvisors.mapper.instances[identifier].source

    def get_proxy(self, identifier: str):
        """ Get the proxy corresponding to the Supervisor identifier. """
        proxy = self.proxies.get(identifier)
        if not proxy:
            instance = self.supvisors.mapper.instances[identifier]
            self.srv_url.update_url(instance.host_id, instance.http_port)
            self.proxies[identifier] = proxy = getRPCInterface(self.srv_url.env)
        return proxy

    def publish(self, publication_message: Tuple):
        """ Publish the event using the XML-RPC interface of the Supervisor instances.
        Isolated instances are not considered.
        No publication to self instance because the event has already been processed. """
        try:
            publication_type = PublicationHeaders(publication_message[0])
        except ValueError:
            self.logger.error(f'SupervisorProxy.publish: unexpected publication={publication_message}')
            return
        # publish the message to all known supvisors instances
        message = self._get_origin(self.local_identifier), publication_message
        for status in self.supvisors.context.instances.values():
            if not status.isolated() and status.identifier != self.local_identifier:
                # if the remote instance is not active, publish only TICK events
                # TODO: retry if already FAILED ?
                if publication_type == PublicationHeaders.TICK or status.has_active_state():
                    self.send_remote_comm_event(status.identifier, message)

    def execute(self, request_message: Tuple) -> None:
        """ Perform the XML-RPC according to the header. """
        request_value, request_body = request_message
        try:
            request_type = RequestHeaders(request_value)
        except ValueError:
            self.logger.error(f'SupervisorProxy.execute: unexpected request={request_value}')
            return
        # send message
        if request_type == RequestHeaders.CHECK_INSTANCE:
            self.check_instance(*request_body)
        elif request_type == RequestHeaders.START_PROCESS:
            self.start_process(*request_body)
        elif request_type == RequestHeaders.STOP_PROCESS:
            self.stop_process(*request_body)
        elif request_type == RequestHeaders.RESTART:
            self.restart(*request_body)
        elif request_type == RequestHeaders.SHUTDOWN:
            self.shutdown(*request_body)
        elif request_type == RequestHeaders.RESTART_SEQUENCE:
            self.restart_sequence(*request_body)
        elif request_type == RequestHeaders.RESTART_ALL:
            self.restart_all(*request_body)
        elif request_type == RequestHeaders.SHUTDOWN_ALL:
            self.shutdown_all(*request_body)

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
        message = PublicationHeaders.AUTHORIZATION.value, (identifier, authorized)
        self.send_remote_comm_event(self.local_identifier, (self._get_origin(identifier), message))

    def _is_authorized(self, identifier: str) -> Optional[bool]:
        """ Get authorization from remote Supvisors instance.
        If the remote Supvisors instance considers the local Supvisors instance as ISOLATED, authorization is denied.

        :param identifier: the identifier of the remote Supvisors instance.
        :return: True if the local Supvisors instance is accepted by the remote Supvisors instance.
        """
        try:
            supvisors_rpc = self.get_proxy(identifier).supvisors
            # check authorization
            local_status_payload = supvisors_rpc.get_instance_info(self.local_identifier)
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
        return instance_state != SupvisorsInstanceStates.ISOLATED

    def _transfer_process_info(self, identifier: str) -> None:
        """ Get the process information from the remote Supvisors instance and post it to the local Supvisors instance.

        :param identifier: the identifier of the remote Supvisors instance.
        :return: None
        """
        # get information about all processes handled by Supervisor
        try:
            all_info = self.get_proxy(identifier).supvisors.get_all_local_process_info()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy._transfer_process_info: failed to get process information'
                              f' from Supvisors={identifier}')
            # the remote Supvisors instance may have gone to a closing state since the previous calls and thus be
            # not able to respond to the request (long shot but not impossible)
            # do NOT set authorized to False in this case or an unwanted isolation may happen
        else:
            # inform local Supvisors about the processes available remotely
            message = PublicationHeaders.ALL_INFO.value, all_info
            self.send_remote_comm_event(self.local_identifier, (self._get_origin(identifier), message))

    def _transfer_states_modes(self, identifier: str) -> None:
        """ Get the states and modes from the remote Supvisors instance and post it to the local Supvisors instance.

        :param identifier: the identifier of the remote Supvisors instance.
        :return: None
        """
        # get authorization from remote Supvisors instance
        try:
            remote_status = self.get_proxy(identifier).supvisors.get_instance_info(identifier)
        except SupervisorProxy.RpcExceptions:
            # Remote Supvisors instance closed in the gap or Supvisors is incorrectly configured
            self.logger.error(f'SupervisorProxy._transfer_states_modes: failed to check Supvisors={identifier}')
        else:
            self.logger.debug(f'SupervisorProxy._transfer_states_modes: remote_status={remote_status}')
            state_modes = {key: remote_status[key] for key in SupervisorProxy.StateModesKeys}
            # provide the local Supvisors with the remote Supvisors instance state and modes
            message = PublicationHeaders.STATE.value, state_modes
            self.send_remote_comm_event(self.local_identifier, (self._get_origin(identifier), message))

    def start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        try:
            self.get_proxy(identifier).supvisors.start_args(namespec, extra_args, False)
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.start_process: failed to start process {namespec} on {identifier}'
                              f' with extra_args="{extra_args}"')

    def stop_process(self, identifier: str, namespec: str) -> None:
        """ Stop process asynchronously. """
        try:
            self.get_proxy(identifier).supervisor.stopProcess(namespec, False)
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.stop_process: failed to stop process {namespec} on {identifier}')

    def restart(self, identifier: str) -> None:
        """ Restart a Supervisor instance asynchronously. """
        try:
            self.get_proxy(identifier).supervisor.restart()
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.restart: failed to restart node {identifier}')

    def shutdown(self, identifier: str) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        try:
            self.get_proxy(identifier).supervisor.shutdown()
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.shutdown: failed to shutdown node {identifier}')

    def restart_sequence(self, identifier: str) -> None:
        """ Ask the Supvisors Master to trigger the DEPLOYMENT phase. """
        try:
            self.get_proxy(identifier).supvisors.restart_sequence()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.restart_sequence: failed to send Supvisors restart_sequence'
                              f' to Master {identifier}')

    def restart_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        try:
            self.get_proxy(identifier).supvisors.restart()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.restart_all: failed to send Supvisors restart'
                              f' to Master {identifier}')

    def shutdown_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to shut down Supvisors. """
        try:
            self.get_proxy(identifier).supvisors.shutdown()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.shutdown_all: failed to send Supvisors shutdown'
                              f' to Master {identifier}')

    def send_remote_comm_event(self, identifier: str, event_data) -> None:
        """ Perform the Supervisor sendRemoteCommEvent. """
        try:
            self.get_proxy(identifier).supervisor.sendRemoteCommEvent(SUPVISORS, json.dumps(event_data))
        except SupervisorProxy.RpcExceptions:
            # expected on restart / shutdown
            self.logger.debug(f'SupervisorProxy.send_remote_comm_event: failed to send to Supervisor={identifier}'
                              f' message={event_data}')
            self.logger.debug(f'SupervisorProxy.send_remote_comm_event: {traceback.format_exc()}')
            # remove the proxy upon failure
            self.supvisors.context.instances[identifier].raise_communication_failure()
            del self.proxies[identifier]


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
        all_coro.extend([self.read_queue(self.receiver.requester_queue, self.check_message),
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

    async def check_discovery_event(self, message):
        """ Transfer the message to the Supervisor thread. """
        self.logger.trace(f'SupvisorsMainLoop.check_discovery_event: message={message}')
        self.proxy.push_message(InternalEventHeaders.DISCOVERY, message)

    async def check_message(self, message) -> None:
        """ Deferred XML-RPC. """
        header, body = message
        try:
            msg_type = InternalEventHeaders(header)
        except ValueError:
            self.logger.error(f'SupvisorsMainLoop.check_message: unexpected header={header}')
        else:
            self.proxy.push_message(msg_type, body)
