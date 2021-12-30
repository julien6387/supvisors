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

from http.client import CannotSendRequest, IncompleteRead
from threading import Event, Thread
from time import time
from typing import Any
from sys import stderr

from supervisor.compat import xmlrpclib
from supervisor.childutils import getRPCInterface
from supervisor.xmlrpc import RPCError

from .supvisorszmq import SupvisorsZmq
from .ttypes import SupvisorsInstanceStates
from .utils import DeferredRequestHeaders, InternalEventHeaders, RemoteCommEvents, SupervisorServerUrl


class SupvisorsMainLoop(Thread):
    """ Class for Supvisors main loop. All inputs are sequenced here.
    The Supervisor logger is not thread-safe so do NOT use it here.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - stop_event: the event used to stop the thread,
        - env: the environment variables linked to Supervisor security access,
        - proxy: the proxy to the internal RPC interface.
    """

    # TICK period in seconds for internal Supvisors heartbeat
    TICK_PERIOD = 5

    # a Supervisor TICK is expected every 5 seconds
    SUPERVISOR_ALERT_TIMEOUT = 10

    # to avoid a long list of exceptions in catches
    RpcExceptions = (KeyError, ValueError, OSError, ConnectionResetError,
                     CannotSendRequest, IncompleteRead, xmlrpclib.Fault, RPCError)

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes.

        :param supvisors: the Supvisors global structure
        """
        # thread attributes
        Thread.__init__(self)
        # create stop event
        self.stop_event = Event()
        # keep a reference to the Supvisors instance and to the environment
        self.supvisors = supvisors
        self.srv_url = SupervisorServerUrl(supvisors.supervisor_data.get_env())
        # create a XML-RPC client to the local Supervisor instance
        self.proxy = getRPCInterface(self.srv_url.env)
        # heartbeat variables
        self.supervisor_time = 0
        self.reference_time = 0.0
        self.reference_counter = 0

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
            # the thread cannot be blocked in a XML-RPC call because of the close_httpservers called
            # just before this stop so join is expected to end properly
            self.join()

    def run(self) -> None:
        """ Contents of the infinite loop. """
        # init heartbeat
        self.reference_time = self.supervisor_time = time()
        self.reference_counter = 0
        # Create zmq sockets
        sockets = SupvisorsZmq(self.supvisors.supvisors_mapper)
        # poll events forever
        while not self.stopping():
            poll_result = sockets.poll()
            # test stop condition again: if Supervisor is stopping,
            # any XML-RPC call would block this thread and the other because of the join
            if not self.stopping():
                # manage heartbeat
                self.manage_heartbeat(sockets.publisher)
                # process events
                self.check_requests(sockets, poll_result)
                self.check_events(sockets, poll_result)
        # close resources gracefully
        sockets.close()

    def manage_heartbeat(self, publisher) -> None:
        """ Send a periodic TICK to other Supvisors instances.
        Supervisor TICK is not reliable for a heartbeat as it may be blocked or delayed by HTTP requests.
        Anyway, a minimum TICK of 5 seconds may be questioned at some point so now it could be lower if necessary. """
        current_time = time()
        current_counter = int((current_time - self.reference_time) / SupvisorsMainLoop.TICK_PERIOD)
        if current_counter > self.reference_counter:
            # send the Supvisors TICK to other Supvisors instances
            self.reference_counter = current_counter
            payload = {'sequence_counter': current_counter, 'when': current_time}
            publisher.send_tick_event(payload)
            # check that Supervisor thread is alive
            supervisor_silence = current_time - self.supervisor_time
            if supervisor_silence > SupvisorsMainLoop.SUPERVISOR_ALERT_TIMEOUT:
                print(f'[ERROR] no TICK received from Supervisor for {supervisor_silence} seconds', file=stderr)

    def check_events(self, sockets, poll_result) -> None:
        """ Forward external Supvisors events to main thread. """
        message = sockets.check_subscriber(poll_result)
        if message:
            # The events received are not processed directly in this thread because it would conflict
            # with the processing in the Supervisor thread, as they use the same data.
            # That's why a RemoteCommunicationEvent is used to push the event in the Supervisor thread.
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_EVENT, json.dumps(message))

    def check_requests(self, sockets, poll_result) -> None:
        """ Defer internal requests. """
        message = sockets.check_puller(poll_result)
        if message:
            header, body = message
            # check publication event or deferred request
            try:
                deferred_request = DeferredRequestHeaders(header)
            except ValueError:
                if header == InternalEventHeaders.TICK.value:
                    # store Supervisor TICK
                    self.supervisor_time = body[1]['when']
                else:
                    # forward the publication
                    sockets.publisher.forward_event(message)
            else:
                if deferred_request == DeferredRequestHeaders.ISOLATE_INSTANCES:
                    # isolation request: disconnect the node from subscriber
                    sockets.disconnect_subscriber(body)
                else:
                    # XML-RPC request
                    self.send_request(deferred_request, body)

    def send_request(self, header: DeferredRequestHeaders, body) -> None:
        """ Perform the XML-RPC according to the header. """
        # first element of body is always the identifier of the destination Supvisors instance
        identifier = body[0]
        instance = self.supvisors.supvisors_mapper.instances[identifier]
        self.srv_url.update_url(instance.host_name, instance.http_port)
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
        """ Check isolation and get all process info asynchronously. """
        try:
            supvisors_rpc = getRPCInterface(self.srv_url.env).supvisors
            # get remote perception of master node and state
            master_identifier = supvisors_rpc.get_master_identifier()
            supvisors_state = supvisors_rpc.get_supvisors_state()['statename']
            # check authorization
            status = supvisors_rpc.get_instance_info(self.supvisors.supvisors_mapper.local_identifier)
            authorized = SupvisorsInstanceStates(status['statecode']) not in [SupvisorsInstanceStates.ISOLATING,
                                                                              SupvisorsInstanceStates.ISOLATED]
            # inform local Supvisors that authorization is available
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH,
                                        f'identifier={identifier} authorized={authorized}'
                                        f' master_identifier={master_identifier} supvisors_state={supvisors_state}')
            # get process info if authorized
            if authorized:
                # get information about all processes handled by Supervisor
                all_info = supvisors_rpc.get_all_local_process_info()
                # post to local Supvisors
                self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_INFO, json.dumps((identifier, all_info)))
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to check Supvisors={identifier}', file=stderr)

    def start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.start_args(namespec, extra_args, False)
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to start process {namespec} on {identifier} with extra_args="{extra_args}"',
                  file=stderr)

    def stop_process(self, identifier: str, namespec: str) -> None:
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.stopProcess(namespec, False)
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to stop process {namespec} on {identifier}', file=stderr)

    def restart(self, identifier: str) -> None:
        """ Restart a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.restart()
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to restart node {identifier}', file=stderr)

    def shutdown(self, identifier: str) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supervisor.shutdown()
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to shutdown node {identifier}', file=stderr)

    def restart_sequence(self, identifier: str) -> None:
        """ Ask the Supvisors Master to trigger the DEPLOYMENT phase. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.restart_sequence()
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to send Supvisors restart_sequence to Master {identifier}', file=stderr)

    def restart_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.restart()
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to send Supvisors restart to Master {identifier}', file=stderr)

    def shutdown_all(self, identifier: str) -> None:
        """ Ask the Supvisors Master to shutdown Supvisors. """
        try:
            proxy = getRPCInterface(self.srv_url.env)
            proxy.supvisors.shutdown()
        except SupvisorsMainLoop.RpcExceptions:
            print(f'[ERROR] failed to send Supvisors shutdown to Master {identifier}', file=stderr)

    def send_remote_comm_event(self, event_type: str, event_data) -> None:
        """ Shortcut for the use of sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(event_type, event_data)
        except SupvisorsMainLoop.RpcExceptions:
            # expected on restart / shutdown
            print(f'[ERROR] failed to send event to Supervisor: {event_type} - {event_data}', file=stderr)
