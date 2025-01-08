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
import time
import traceback
from enum import Enum
from http.client import HTTPException
from typing import Any, Dict, Optional, Tuple
from xmlrpc.client import ServerProxy

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

# life expectation for the local proxy
# Supervisor close any HTTP channel after 30 minutes without activity
LOCAL_PROXY_DURATION = 20 * 60


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
        self._proxy: Optional[ServerProxy] = None
        self.last_used: float = time.monotonic()

    @property
    def logger(self) -> Logger:
        """ Shortcut to the Supvisors logger. """
        return self.supvisors.logger

    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.supvisors.mapper.local_identifier

    @property
    def proxy(self) -> ServerProxy:
        """ Get the Supervisor proxy. """
        if not self._proxy:
            self._proxy = self._get_proxy()
        elif self.status.supvisors_id.identifier == self.local_identifier:
            # WARN: The proxy to the local Supervisor is a LOT less used than the others and is really subject
            #       to be broken by the http_channel.kill_zombies (supervisor/medusa/http_server.py) that will close
            #       the channel after 30 minutes of inactivity (magic number).
            #       So, let's re-create the local proxy once every 20 minutes.
            #       All other proxies will be maintained through to the TICK publication.
            if time.monotonic() - self.last_used > LOCAL_PROXY_DURATION:
                self.logger.debug(f'SupervisorProxy.proxy: recreate local Supervisor proxy')
                self._proxy = self._get_proxy()
                self.last_used = time.monotonic()
        return self._proxy

    def _get_proxy(self) -> ServerProxy:
        """ Get the proxy corresponding to the Supervisor identifier. """
        instance_id = self.status.supvisors_id
        # SupervisorServerUrl contains the environment variables linked to Supervisor security access
        srv_url: SupervisorServerUrl = SupervisorServerUrl(self.supvisors.supervisor_data.get_env())
        srv_url.update_url(instance_id.host_id, instance_id.http_port)
        return getRPCInterface(srv_url.env)

    def _get_origin(self, from_identifier: str) -> Tuple[str, Ipv4Address]:
        """ Return the identification of the Supvisors instance. """
        return self.supvisors.mapper.instances[from_identifier].source

    def xml_rpc(self, fct_name: str, fct, args):
        """ Common exception handling on XML-RPC methods. """
        # reset the proxy usage time
        self.last_used = time.monotonic()
        # call the XML-RPC
        try:
            return fct(*args)
        except (RPCError, xmlrpclib.Fault) as exc:
            # the request is unexpected by the remote instance and the XML-RPC error is raised
            # no impact to the proxy
            self.logger.warn(f'SupervisorProxy.xml_rpc: Supervisor={self.status.usage_identifier}'
                             f' {fct_name}{args} failed - {str(exc)}')
            self.logger.debug(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
            return None
        except (OSError, HTTPException) as exc:
            # transport issue due to network or remote Supervisor failure (includes a bunch of exceptions, such as
            # socket.gaierror, ConnectionResetError, ConnectionRefusedError, CannotSendRequest, IncompleteRead, etc.)
            # also raised if the HTTP channel has been closed by the Supervisor kill_zombies (30 minutes inactivity)
            # the proxy is not operational - error log only if instance is active
            log_level = LevelsByName.ERRO if self.status.has_active_state() else LevelsByName.DEBG
            message = f'SupervisorProxy.xml_rpc: Supervisor={self.status.usage_identifier} not reachable - {str(exc)}'
            self.logger.log(log_level, message)
            self.logger.debug(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
            # NOTE: when the other end is not ready, the ServerProxy is not valid and cannot be reused, so reset it
            #       further calls would raise CannotSendRequest exceptions
            self._proxy = None
            raise SupervisorProxyException
        except (KeyError, ValueError, TypeError) as exc:
            # JSON serialization issue / implementation error
            self.logger.error(f'SupervisorProxy.xml_rpc: Supervisor={self.status.usage_identifier}'
                              f' {fct_name}{args} data error - {str(exc)}')
            self.logger.error(f'SupervisorProxy.xml_rpc: {traceback.format_exc()}')
            # reset the proxy, same reason as above
            self._proxy = None
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

        This is needed for the local Supvisors instance too because Supervisor does not provide the initial
        status on the local processes through the notification function.

        :return: None.
        """
        # additional information sent internally depends on the actual authorization
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
        self.logger.debug(f'SupervisorProxy.is_authorized: local_status_payload={local_status_payload}')
        # the remote Supvisors instance is likely starting, restarting or shutting down so give it a chance
        if local_status_payload is None:
            return None
        # check the local Supvisors instance state as seen by the remote Supvisors instance
        state = local_status_payload[0]['statecode']
        try:
            instance_state = SupvisorsInstanceStates(state)
        except ValueError:
            self.logger.error(f'SupervisorProxy.is_authorized: unknown Supvisors instance state={state}')
            return False
        # authorization is granted if the remote Supvisors instances did not isolate the local Supvisors instance
        return instance_state != SupvisorsInstanceStates.ISOLATED

    def _transfer_states_modes(self) -> None:
        """ Get the states and modes from the remote Supvisors instance and post it to the local Supvisors instance.

        :return: None.
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

        :return: None.
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
        while not self.event.is_set():
            try:
                event = self.queue.get(timeout=SupervisorProxyThread.QUEUE_TIMEOUT)
            except queue.Empty:
                self.logger.blather('SupervisorProxyThread.run: nothing received')
            else:
                self.process_event(event)
        # inform the proxy server that the thread is going to end
        self.supvisors.rpc_handler.proxy_server.on_proxy_closing(self.status.identifier)
        self.logger.debug('SupervisorProxyThread.run: exiting main loop'
                          f' for identifier={self.status.usage_identifier}')

    def handle_exception(self):
        """ Inform the local Supvisors instance about the remote proxy failure. """
        if self.status.identifier == self.local_identifier:
            # expected only when stopping
            self.logger.debug('SupervisorProxyThread.handle_exception: local failure')
        elif self.status.has_active_state():
            # not needed if not active yet
            origin = self._get_origin(self.status.identifier)
            message = NotificationHeaders.INSTANCE_FAILURE.value, None
            self.supvisors.rpc_handler.proxy_server.push_notification((origin, message))

    def process_event(self, event):
        """ Proceed with the event depending on its type. """
        try:
            event_type, (source, event_body) = event
            if event_type == InternalEventHeaders.REQUEST:
                self.execute(event_body)
            elif event_type == InternalEventHeaders.PUBLICATION:
                self.publish(source, event_body)
            elif event_type == InternalEventHeaders.NOTIFICATION:
                # direct forward without checking
                # the local Supervisor is expected to be always non-isolated and active
                self.send_remote_comm_event(SUPVISORS_NOTIFICATION, (source, event_body))
        except SupervisorProxyException:
            self.handle_exception()


class SupervisorProxyServer:
    """ Manage the Supervisor proxies and distribute the messages. """

    # enable a specific proxy thread
    klass = SupervisorProxyThread

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # the proxy dictionary is protected by a mutex because there is a multi-threads usage
        self.proxies: Dict[str, SupervisorProxyThread] = {}
        self.mutex: threading.RLock = threading.RLock()
        # do not allow the creation of a new proxy when stop is requested
        self.stop_event: threading.Event = threading.Event()

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
        # get the existing proxy
        with self.mutex:
            proxy = self.proxies.get(identifier)
        status: SupvisorsInstanceStatus = self.supvisors.context.instances[identifier]
        # do not allow the creation of a new proxy when stop is requested
        # WARN: using is_alive is NOT reliable as a condition to restart a closed proxy
        if not proxy and not status.isolated and not self.stop_event.is_set():
            # create and start the proxy thread
            proxy = self.klass(status, self.supvisors)
            proxy.start()
            with self.mutex:
                self.proxies[identifier] = proxy
        elif proxy and status.isolated:
            # destroy the proxy of an ISOLATED Supvisors instance
            proxy.stop()
            proxy.join()
            with self.mutex:
                del self.proxies[identifier]
            proxy = None
        return proxy

    def on_proxy_closing(self, identifier: str):
        """ Clear the proxy reference when its thread is about to end. """
        with self.mutex:
            del self.proxies[identifier]

    def stop(self):
        """ Stop all the proxy threads. """
        # prevent the creation of new threads, especially for INSTANCE_FAILURE notification
        self.stop_event.set()
        # stop all threads
        # NOTE: work on copy to avoid a deadlock
        with self.mutex:
            self.logger.debug(f'SupervisorProxyServer.stop: proxies={list(self.proxies.keys())}')
            proxies = list(self.proxies.values())
        for proxy in proxies:
            proxy.stop()
        for proxy in proxies:
            proxy.join()
        # at this point, the proxy dictionary should be empty
        # if it's not the case, it should be assumed that the thread died due to an uncaught exception
        with self.mutex:
            if self.proxies:
                self.logger.error(f'SupervisorProxyServer.stop: proxies not empty {list(self.proxies.keys())}')


    def push_request(self, identifier: str, message):
        """ Send an XML-RPC request to a Supervisor proxy.

        :param identifier: the identifier of the Supvisors instance to request.
        :param message: the message to push.
        :return: None.
        """
        proxy = self.get_proxy(identifier)
        if proxy:
            proxy.push_message((InternalEventHeaders.REQUEST, (self.local_identifier, message)))

    def push_publication(self, message):
        """ Send a publication to all remote Supervisor proxies.

        :param message: the message to publish.
        :return: None.
        """
        for identifier in self.supvisors.mapper.instances:
            # no publication to self instance because the event has already been processed.
            if identifier != self.local_identifier:
                proxy = self.get_proxy(identifier)
                if proxy:
                    proxy.push_message((InternalEventHeaders.PUBLICATION, (self.local_identifier, message)))

    def push_notification(self, message):
        """ Send a discovery event to all remote Supervisor proxies.

        :param message: the message to notify.
        :return: None.
        """
        proxy = self.get_proxy(self.local_identifier)
        if proxy:
            proxy.push_message((InternalEventHeaders.NOTIFICATION, message))
