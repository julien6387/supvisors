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
import queue
import threading
import traceback
from enum import Enum
from http.client import CannotSendRequest, IncompleteRead
from typing import Any, Dict, Optional, Tuple

from supervisor.childutils import getRPCInterface
from supervisor.compat import xmlrpclib
from supervisor.loggers import Logger
from supervisor.xmlrpc import RPCError

from supvisors.instancestatus import SupvisorsInstanceStatus
from supvisors.ttypes import Ipv4Address, RequestHeaders, PublicationHeaders, SupvisorsInstanceStates, SUPVISORS
from supvisors.utils import SupervisorServerUrl

# List of keys useful to build a SupvisorsState event
StateModesKeys = ['fsm_statecode', 'discovery_mode', 'master_identifier', 'starting_jobs', 'stopping_jobs']


class InternalEventHeaders(Enum):
    """ Event type for deferred XML-RPCs. """
    REQUEST, PUBLICATION, DISCOVERY = range(3)


class SupervisorProxy:
    """ xmlrpclib.ServerProxy is not thread-safe so all requests are pushed to a synchronous queue
    so that the requests are served and the async loop is not blocked. """

    # to avoid a long list of exceptions in catches
    RpcExceptions = (KeyError, ValueError, OSError, ConnectionResetError,
                     CannotSendRequest, IncompleteRead, xmlrpclib.Fault, RPCError)

    def __init__(self, identifier: str, supvisors: Any):
        """ Initialization of the attributes. """
        self.identifier: str = identifier
        self.supvisors = supvisors
        # create an XML-RPC client to the local Supervisor instance
        self.instance_status: SupvisorsInstanceStatus = supvisors.context.instances[identifier]
        self.proxy = self._get_proxy()

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.supvisors.mapper.local_identifier

    def _get_proxy(self):
        """ Get the proxy corresponding to the Supervisor identifier. """
        instance_id = self.instance_status.supvisors_id
        # SupervisorServerUrl contains the environment variables linked to Supervisor security access,
        srv_url: SupervisorServerUrl = SupervisorServerUrl(self.supvisors.supervisor_data.get_env())
        srv_url.update_url(instance_id.host_id, instance_id.http_port)
        return getRPCInterface(srv_url.env)

    def _get_origin(self, from_identifier: str) -> Tuple[str, Ipv4Address]:
        """ Return the identification of the Supvisors instance. """
        return self.supvisors.mapper.instances[from_identifier].source

    def send_remote_comm_event(self, event) -> None:
        """ Perform the Supervisor sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(SUPVISORS, json.dumps(event))
        except SupervisorProxy.RpcExceptions:
            # expected on restart / shutdown
            self.logger.debug(f'SupervisorProxy.send_remote_comm_event: failed to send to Supervisor={self.identifier}'
                              f' message={event}')
            self.logger.debug(f'SupervisorProxy.send_remote_comm_event: {traceback.format_exc()}')
            self.instance_status.rpc_failure = True
        else:
            self.instance_status.rpc_failure = False

    def publish(self, from_identifier: str, publication_message: Tuple):
        """ Publish the event using the XML-RPC interface of the Supervisor instances. """
        try:
            publication_type = PublicationHeaders(publication_message[0])
        except ValueError:
            self.logger.error(f'SupervisorRemoteProxy.publish: unexpected publication={publication_message}')
            return
        # publish the message to the supvisors instance
        # if the remote instance is not active, publish only TICK events
        if publication_type == PublicationHeaders.TICK or self.instance_status.has_active_state():
            message = self._get_origin(from_identifier), publication_message
            self.send_remote_comm_event(message)

    def execute(self, request_message: Tuple) -> None:
        """ Perform the XML-RPC according to the header. """
        try:
            request_type = RequestHeaders(request_message[0])
        except ValueError:
            self.logger.error(f'SupervisorProxy.execute: unexpected request={request_message[0]}')
            return
        # send message
        if request_type == RequestHeaders.CHECK_INSTANCE:
            self.check_instance()
        elif request_type == RequestHeaders.START_PROCESS:
            self.start_process(*request_message[1])
        elif request_type == RequestHeaders.STOP_PROCESS:
            self.stop_process(*request_message[1])
        elif request_type == RequestHeaders.RESTART:
            self.restart()
        elif request_type == RequestHeaders.SHUTDOWN:
            self.shutdown()
        elif request_type == RequestHeaders.RESTART_SEQUENCE:
            self.restart_sequence()
        elif request_type == RequestHeaders.RESTART_ALL:
            self.restart_all()
        elif request_type == RequestHeaders.SHUTDOWN_ALL:
            self.shutdown_all()

    def check_instance(self) -> None:
        """ Check isolation and get all process info from the Supvisors instance.

        :return: None.
        """
        authorized = self._is_authorized()
        self.logger.info(f'SupervisorProxy.check_instance: identifier={self.identifier} authorized={authorized}')
        if authorized:
            self._transfer_states_modes()
            self._transfer_process_info()
        # inform local Supvisors that authorization result is available
        # NOTE: use the proxy server to switch to the relevant proxy thread
        message = PublicationHeaders.AUTHORIZATION.value, authorized
        self.supvisors.rpc_handler.proxy_server.post_event(self.identifier, self.local_identifier, message)

    def _is_authorized(self) -> Optional[bool]:
        """ Get authorization from the remote Supvisors instance.
        If the remote Supvisors instance considers the local Supvisors instance as ISOLATED, authorization is denied.

        :return: True if the local Supvisors instance is accepted by the remote Supvisors instance.
        """
        try:
            # check authorization
            local_status_payload = self.proxy.supvisors.get_instance_info(self.local_identifier)
            self.logger.debug(f'SupervisorProxy._is_authorized: local_status_payload={local_status_payload}')
        except SupervisorProxy.RpcExceptions:
            # Remote Supvisors instance closed in the gap or Supvisors is incorrectly configured
            self.logger.error(f'SupervisorProxy._is_authorized: failed to check Supvisors={self.identifier}')
            self.logger.debug(f'SupervisorProxy._is_authorized: {traceback.format_exc()}')
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

    def _transfer_states_modes(self) -> None:
        """ Get the states and modes from the remote Supvisors instance and post it to the local Supvisors instance.

        :return: None
        """
        try:
            remote_status = self.proxy.supvisors.get_instance_info(self.identifier)
        except SupervisorProxy.RpcExceptions:
            # Remote Supvisors instance closed in the gap or Supvisors is incorrectly configured
            self.logger.error('SupervisorProxy._transfer_states_modes: failed to get self perception'
                              f' from Supvisors={self.identifier}')
            self.logger.debug(f'SupervisorProxy._transfer_states_modes: {traceback.format_exc()}')
        else:
            self.logger.debug(f'SupervisorProxy._transfer_states_modes: remote_status={remote_status}')
            state_modes = {key: remote_status[key] for key in StateModesKeys}
            # provide the local Supvisors with the remote Supvisors instance state and modes
            # NOTE: use the proxy server to switch to the relevant proxy thread
            message = PublicationHeaders.STATE.value, state_modes
            self.supvisors.rpc_handler.proxy_server.post_event(self.identifier, self.local_identifier, message)

    def _transfer_process_info(self) -> None:
        """ Get the process information from the remote Supvisors instance and post it to the local Supvisors instance.

        :return: None
        """
        # get information about all processes handled by the remote Supervisor
        try:
            all_info = self.proxy.supvisors.get_all_local_process_info()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy._transfer_process_info: failed to get process information'
                              f' from Supvisors={self.identifier}')
            self.logger.debug(f'SupervisorProxy._transfer_process_info: {traceback.format_exc()}')
            # the remote Supvisors instance may have gone to a closing state since the previous calls and thus be
            # not able to respond to the request (long shot but not impossible)
            # do NOT set authorized to False in this case or an unwanted isolation may happen
        else:
            # inform local Supvisors about the processes available remotely
            # NOTE: use the proxy server to switch to the relevant proxy thread
            message = PublicationHeaders.ALL_INFO.value, all_info
            self.supvisors.rpc_handler.proxy_server.post_event(self.identifier, self.local_identifier, message)

    def start_process(self, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        try:
            self.proxy.supvisors.start_args(namespec, extra_args, False)
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.start_process: failed to start process {namespec} on {self.identifier}'
                              f' with extra_args="{extra_args}"')
            self.logger.debug(f'SupervisorProxy.start_process: {traceback.format_exc()}')

    def stop_process(self, namespec: str) -> None:
        """ Stop process asynchronously. """
        try:
            self.proxy.supervisor.stopProcess(namespec, False)
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.stop_process: failed to stop process {namespec} on {self.identifier}')
            self.logger.debug(f'SupervisorProxy.stop_process: {traceback.format_exc()}')

    def restart(self) -> None:
        """ Restart a Supervisor instance asynchronously. """
        try:
            self.proxy.supervisor.restart()
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.restart: failed to restart node {self.identifier}')
            self.logger.debug(f'SupervisorProxy.restart: {traceback.format_exc()}')

    def shutdown(self) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        try:
            self.proxy.supervisor.shutdown()
        except SupervisorProxy.RpcExceptions:
            self.logger.error(f'SupervisorProxy.shutdown: failed to shutdown node {self.identifier}')
            self.logger.debug(f'SupervisorProxy.shutdown: {traceback.format_exc()}')

    def restart_sequence(self) -> None:
        """ Ask the Supvisors Master to trigger the DEPLOYMENT phase. """
        try:
            self.proxy.supvisors.restart_sequence()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.restart_sequence: failed to send Supvisors restart_sequence'
                              f' to Master {self.identifier}')
            self.logger.debug(f'SupervisorProxy.restart_sequence: {traceback.format_exc()}')

    def restart_all(self) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        try:
            self.proxy.supvisors.restart()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.restart_all: failed to send Supvisors restart'
                              f' to Master {self.identifier}')
            self.logger.debug(f'SupervisorProxy.restart_all: {traceback.format_exc()}')

    def shutdown_all(self) -> None:
        """ Ask the Supvisors Master to shut down Supvisors. """
        try:
            self.proxy.supvisors.shutdown()
        except SupervisorProxy.RpcExceptions:
            self.logger.error('SupervisorProxy.shutdown_all: failed to send Supvisors shutdown'
                              f' to Master {self.identifier}')
            self.logger.debug(f'SupervisorProxy.shutdown_all: {traceback.format_exc()}')


class SupervisorProxyThread(threading.Thread, SupervisorProxy):
    """ Wrapper of the SupervisorProxy. """

    QUEUE_TIMEOUT = 1.0

    def __init__(self, identifier: str, supvisors: Any):
        """ Initialization of the attributes. """
        threading.Thread.__init__(self, daemon=True)
        SupervisorProxy.__init__(self, identifier, supvisors)
        # thread logic
        self.queue: queue.Queue = queue.Queue()
        self.event: threading.Event = threading.Event()

    def push_message(self, message):
        """ Add an event to send to a Supervisor instance through an XML-RPC. """
        self.queue.put_nowait(message)

    def stop(self):
        """ Set the event to stop the main loop. """
        self.event.set()

    def run(self):
        """ Proxy main loop. """
        self.logger.info(f'SupervisorProxyThread.run: entering main loop for identifier={self.identifier}')
        while not self.event.is_set():
            try:
                event_type, (source, event_body) = self.queue.get(timeout=self.QUEUE_TIMEOUT)
            except queue.Empty:
                self.logger.blather('SupervisorProxyThread.run: nothing received')
            else:
                if event_type == InternalEventHeaders.REQUEST:
                    self.execute(event_body)
                elif event_type == InternalEventHeaders.PUBLICATION:
                    self.publish(source, event_body)
                elif event_type == InternalEventHeaders.DISCOVERY:
                    # direct forward without check
                    # the local Supervisor is expected to be always non-isolated and active
                    self.send_remote_comm_event((source, event_body))
        self.logger.info(f'SupervisorProxyThread.run: exiting main loop for identifier={self.identifier}')


class SupervisorProxyServer:
    """ Manage the Supervisor proxies and distribute the messages. """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.proxies: Dict[str, SupervisorProxyThread] = {}

    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.supvisors.mapper.local_identifier

    def get_proxy(self, identifier: str) -> Optional[SupervisorProxyThread]:
        """ Return the Supervisor proxy corresponding to the identifier.

        It is managed dynamically because of the Supvisors discovery mode.
        No proxy is available for an ISOLATED instance.
        """
        proxy = self.proxies.get(identifier)
        isolated = self.supvisors.context.instances[identifier].isolated
        if not isolated and (not proxy or not proxy.is_alive()):
            # create and start the proxy thread
            self.proxies[identifier] = proxy = SupervisorProxyThread(identifier, self.supvisors)
            proxy.start()
        elif proxy and isolated:
            # destroy the proxy of an ISOLATED Supvisors instance
            proxy.stop()
            proxy.join()
            del self.proxies[identifier]
            proxy = None
        return proxy

    def stop(self):
        """ Stop all the proxy threads. """
        for proxy in self.proxies.values():
            proxy.stop()
        for proxy in self.proxies.values():
            proxy.join()

    def post_request(self, identifier: str, message):
        """ Send an XML-RPC request to a Supervisor proxy.

        :param identifier: the identifier of the Supvisors instance to request.
        :param message: the message to send.
        :return: None.
        """
        proxy = self.get_proxy(identifier)
        if proxy:
            proxy.push_message((InternalEventHeaders.REQUEST, (self.local_identifier, message)))

    def publish(self, message):
        """ Send a publication to all remote Supervisor proxies.

        :param message: the message to send.
        :return: None.
        """
        for identifier in self.supvisors.mapper.instances:
            # No publication to self instance because the event has already been processed.
            if identifier != self.local_identifier:
                self.post_event(self.local_identifier, identifier, message)

    def post_event(self, from_identifier: str, to_identifier: str, message) -> None:
        """ Send a publication to a Supervisor proxy.

        :param from_identifier: the source of the publication.
        :param to_identifier: the destination of the publication.
        :param message: the message to send.
        :return: None.
        """
        proxy = self.get_proxy(to_identifier)
        if proxy:
            proxy.push_message((InternalEventHeaders.PUBLICATION, (from_identifier, message)))

    def post_discovery(self, message):
        """ Send a discovery event to all remote Supervisor proxies.

        :param message: the message to send.
        :return: None.
        """
        proxy = self.get_proxy(self.local_identifier)
        if proxy:
            proxy.push_message((InternalEventHeaders.DISCOVERY, message))
