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
from http.client import HTTPException
from typing import Any, Dict, Optional, Tuple

from supervisor.childutils import getRPCInterface
from supervisor.compat import xmlrpclib
from supervisor.loggers import Logger, LevelsByName
from supervisor.xmlrpc import RPCError

from supvisors.instancestatus import SupvisorsInstanceStatus
from supvisors.ttypes import (Ipv4Address, SupvisorsInstanceStates,
                              SUPVISORS_PUBLICATION, SUPVISORS_NOTIFICATION,
                              RequestHeaders, PublicationHeaders, NotificationHeaders)
from supvisors.utils import SupervisorServerUrl

# List of keys useful to build a SupvisorsState event
StateModesKeys = ['fsm_statecode', 'discovery_mode', 'master_identifier', 'starting_jobs', 'stopping_jobs']


class InternalEventHeaders(Enum):
    """ Event type for deferred XML-RPCs. """
    REQUEST, PUBLICATION, NOTIFICATION = range(3)


class SupervisorProxyException(Exception):
    pass


class SupervisorProxy:
    """ xmlrpclib.ServerProxy is not thread-safe so all requests are pushed to a synchronous queue
    so that the requests are served and the async loop is not blocked. """

    def __init__(self, status: SupvisorsInstanceStatus, supvisors: Any):
        """ Initialization of the attributes. """
        self.status: SupvisorsInstanceStatus = status
        self.supvisors = supvisors
        # create an XML-RPC client to the local Supervisor instance
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
        instance_id = self.status.supvisors_id
        # SupervisorServerUrl contains the environment variables linked to Supervisor security access,
        srv_url: SupervisorServerUrl = SupervisorServerUrl(self.supvisors.supervisor_data.get_env())
        srv_url.update_url(instance_id.host_id, instance_id.http_port)
        return getRPCInterface(srv_url.env)

    def _get_origin(self, from_identifier: str) -> Tuple[str, Ipv4Address]:
        """ Return the identification of the Supvisors instance. """
        return self.supvisors.mapper.instances[from_identifier].source

    def xml_rpc(self, fct_name: str, fct, args):
        """ Common exception handling on XML-RPC methods. """
        try:
            return fct(*args)
        except RPCError as exc:
            # the request is unexpected by an operational remote instance and the XML-RPC error is raised
            # no impact in proxy
            self.logger.warn(f'SupervisorProxy.xml_rpc: Supervisor={self.status.usage_identifier}'
                             f' {fct_name}{args} failed - {str(exc)}')
            self.logger.debug(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
        except (OSError, HTTPException) as exc:
            # transport issue due to network or remote Supervisor failure (includes a bunch of exceptions, such as
            # socket.gaierror, ConnectionResetError, ConnectionRefusedError, CannotSendRequest, IncompleteRead, etc.)
            # the proxy is not operational - error log only if instance is active
            log_level = LevelsByName.ERRO if self.status.has_active_state() else LevelsByName.DEBG
            message = f'SupervisorProxy.xml_rpc: Supervisor={self.status.usage_identifier} not reachable - {str(exc)}'
            self.logger.log(log_level, message)
            self.logger.debug(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
            raise SupervisorProxyException
        except xmlrpclib.Fault as exc:
            # undoubtedly an implementation error (unknown method)
            self.logger.critical(f'SupervisorProxy.xml_rpc: software error - {str(exc)}')
            self.logger.error(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
            raise SupervisorProxyException
        except (KeyError, ValueError, TypeError) as exc:
            # JSON serialization issue / implementation error
            self.logger.error(f'SupervisorProxy.xml_rpc: data error using {fct_name}{args} - {str(exc)}')
            self.logger.error(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
            raise SupervisorProxyException

    def send_remote_comm_event(self, event_type: str, event) -> None:
        """ Send a user message to the remote Supervisor using the sendRemoteCommEvent XML-RPC. """
        self.xml_rpc('supervisor.sendRemoteCommEvent',
                     self.proxy.supervisor.sendRemoteCommEvent,
                     (event_type, json.dumps(event)))

    def publish(self, from_identifier: str, publication_message: Tuple):
        """ Publish the event using the XML-RPC interface of the Supervisor instances. """
        try:
            publication_type = PublicationHeaders(publication_message[0])
        except ValueError:
            self.logger.error(f'SupervisorRemoteProxy.publish: unexpected publication={publication_message}')
            return
        # publish the message to the supvisors instance
        # if the remote instance is not active, publish only TICK events
        if publication_type == PublicationHeaders.TICK or self.status.has_active_state():
            message = self._get_origin(from_identifier), publication_message
            self.send_remote_comm_event(SUPVISORS_PUBLICATION, message)

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
        self.logger.info(f'SupervisorProxy.check_instance: identifier={self.status.usage_identifier}'
                         f' authorized={authorized}')
        if authorized:
            self._transfer_states_modes()
            self._transfer_process_info()
        # inform local Supvisors that authorization result is available
        # NOTE: use the proxy server to switch to the relevant proxy thread
        origin = self._get_origin(self.status.identifier)
        message = NotificationHeaders.AUTHORIZATION.value, authorized
        self.supvisors.rpc_handler.proxy_server.push_notification((origin, message))

    def _is_authorized(self) -> Optional[bool]:
        """ Get authorization from the remote Supvisors instance.
        If the remote Supvisors instance considers the local Supvisors instance as ISOLATED, authorization is denied.

        :return: True if the local Supvisors instance is accepted by the remote Supvisors instance.
        """
        # check authorization
        local_status_payload = self.xml_rpc('supvisors.get_instance_info',
                                            self.proxy.supvisors.get_instance_info,
                                            (self.local_identifier,))
        self.logger.debug(f'SupervisorProxy._is_authorized: local_status_payload={local_status_payload}')
        # the remote Supvisors instance is likely starting, restarting or shutting down so give it a chance
        if local_status_payload is None:
            return None
        # check the local Supvisors instance state as seen by the remote Supvisors instance
        state = local_status_payload[0]['statecode']
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
        remote_status = self.xml_rpc('supvisors.get_instance_info',
                                     self.proxy.supvisors.get_instance_info,
                                     (self.status.identifier,))
        self.logger.debug(f'SupervisorProxy._transfer_states_modes: remote_status={remote_status}')
        state_modes = None
        if remote_status:
            state_modes = {key: remote_status[0][key] for key in StateModesKeys}
        # provide the local Supvisors with the remote Supvisors instance state and modes
        # NOTE: use the proxy server to switch to the relevant proxy thread
        origin = self._get_origin(self.status.identifier)
        message = NotificationHeaders.STATE.value, state_modes
        self.supvisors.rpc_handler.proxy_server.push_notification((origin, message))

    def _transfer_process_info(self) -> None:
        """ Get the process information from the remote Supvisors instance and post it to the local Supvisors instance.

        :return: None
        """
        # get information about all processes handled by the remote Supervisor
        all_info = self.xml_rpc('supvisors.get_all_local_process_info',
                                self.proxy.supvisors.get_all_local_process_info,
                                ())
        # inform local Supvisors about the processes available remotely
        # NOTE: use the proxy server to switch to the relevant proxy thread
        origin = self._get_origin(self.status.identifier)
        message = NotificationHeaders.ALL_INFO.value, all_info
        self.supvisors.rpc_handler.proxy_server.push_notification((origin, message))

    def start_process(self, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        self.xml_rpc('supvisors.start_args', self.proxy.supvisors.start_args, (namespec, extra_args, False))

    def stop_process(self, namespec: str) -> None:
        """ Stop process asynchronously. """
        self.xml_rpc('supervisor.stopProcess', self.proxy.supervisor.stopProcess, (namespec, False))

    def restart(self) -> None:
        """ Restart a Supervisor instance asynchronously. """
        self.xml_rpc('supervisor.restart', self.proxy.supervisor.restart, ())

    def shutdown(self) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        self.xml_rpc('supervisor.shutdown', self.proxy.supervisor.shutdown, ())

    def restart_sequence(self) -> None:
        """ Ask the Supvisors Master to trigger the DEPLOYMENT phase. """
        self.xml_rpc('supvisors.restart_sequence', self.proxy.supvisors.restart_sequence, ())

    def restart_all(self) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        self.xml_rpc('supvisors.restart', self.proxy.supvisors.restart, ())

    def shutdown_all(self) -> None:
        """ Ask the Supvisors Master to shut down Supvisors. """
        self.xml_rpc('supvisors.shutdown', self.proxy.supvisors.shutdown, ())


class SupervisorProxyThread(threading.Thread, SupervisorProxy):
    """ Wrapper of the SupervisorProxy. """

    QUEUE_TIMEOUT = 1.0

    def __init__(self, status: SupvisorsInstanceStatus, supvisors: Any):
        """ Initialization of the attributes. """
        threading.Thread.__init__(self, daemon=True)
        SupervisorProxy.__init__(self, status, supvisors)
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
        self.logger.debug('SupervisorProxyThread.run: entering main loop'
                          f' for identifier={self.status.usage_identifier}')
        try:
            while not self.event.is_set():
                try:
                    event = self.queue.get(timeout=self.QUEUE_TIMEOUT)
                except queue.Empty:
                    self.logger.blather('SupervisorProxyThread.run: nothing received')
                else:
                    self.process_event(event)
        except SupervisorProxyException:
            # inform the local Supvisors instance about the remote proxy failure, thus the remote Supvisors instance
            # not needed if not active yet
            if self.status.identifier != self.local_identifier and self.status.has_active_state():
                origin = self._get_origin(self.status.identifier)
                message = NotificationHeaders.INSTANCE_FAILURE.value, None
                self.supvisors.rpc_handler.proxy_server.push_notification((origin, message))
        self.logger.debug('SupervisorProxyThread.run: exiting main loop'
                          f' for identifier={self.status.usage_identifier}')

    def process_event(self, event):
        """ Proceed with the event depending on its type. """
        event_type, (source, event_body) = event
        if event_type == InternalEventHeaders.REQUEST:
            self.execute(event_body)
        elif event_type == InternalEventHeaders.PUBLICATION:
            self.publish(source, event_body)
        elif event_type == InternalEventHeaders.NOTIFICATION:
            # direct forward without checking
            # the local Supervisor is expected to be always non-isolated and active
            self.send_remote_comm_event(SUPVISORS_NOTIFICATION, (source, event_body))


class SupervisorProxyServer:
    """ Manage the Supervisor proxies and distribute the messages. """

    # enable a specific proxy thread
    klass = SupervisorProxyThread

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.proxies: Dict[str, SupervisorProxyThread] = {}

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

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
        status: SupvisorsInstanceStatus = self.supvisors.context.instances[identifier]
        if not status.isolated and (not proxy or not proxy.is_alive()):
            # create and start the proxy thread
            self.proxies[identifier] = proxy = self.klass(status, self.supvisors)
            proxy.start()
        elif proxy and status.isolated:
            # destroy the proxy of an ISOLATED Supvisors instance
            proxy.stop()
            proxy.join()
            del self.proxies[identifier]
            proxy = None
        return proxy

    def stop(self):
        """ Stop all the proxy threads. """
        self.logger.debug(f'SupervisorProxyServer.stop: {list(self.proxies.keys())}')
        for proxy in self.proxies.values():
            proxy.stop()
        for proxy in self.proxies.values():
            proxy.join()

    def push_request(self, identifier: str, message):
        """ Send an XML-RPC request to a Supervisor proxy.

        :param identifier: the identifier of the Supvisors instance to request.
        :param message: the message to send.
        :return: None.
        """
        proxy = self.get_proxy(identifier)
        if proxy:
            proxy.push_message((InternalEventHeaders.REQUEST, (self.local_identifier, message)))

    def push_publication(self, message):
        """ Send a publication to all remote Supervisor proxies.

        :param message: the message to send.
        :return: None.
        """
        for identifier in self.supvisors.mapper.instances:
            # No publication to self instance because the event has already been processed.
            if identifier != self.local_identifier:
                proxy = self.get_proxy(identifier)
                if proxy:
                    proxy.push_message((InternalEventHeaders.PUBLICATION, (self.local_identifier, message)))

    def push_notification(self, message):
        """ Send a discovery event to all remote Supervisor proxies.

        :param message: the message to send.
        :return: None.
        """
        proxy = self.get_proxy(self.local_identifier)
        proxy.push_message((InternalEventHeaders.NOTIFICATION, message))
