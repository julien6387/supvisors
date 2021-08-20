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
from typing import Any
from sys import stderr

from supervisor.compat import xmlrpclib
from supervisor.xmlrpc import RPCError

from .rpcrequests import getRPCInterface
from .supvisorszmq import SupvisorsZmq
from .ttypes import AddressStates
from .utils import DeferredRequestHeaders, RemoteCommEvents


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
        self.env = supvisors.info_source.get_env()
        # create a XML-RPC client to the local Supervisor instance
        self.proxy = getRPCInterface('localhost', self.env)

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
        # Create zmq sockets
        sockets = SupvisorsZmq(self.supvisors)
        # poll events forever
        while not self.stopping():
            poll_result = sockets.poll()
            # test stop condition again: if Supervisor is stopping,
            # any XML-RPC call would block this thread, and the other
            # because of the join
            if not self.stopping():
                self.check_requests(sockets, poll_result)
                self.check_events(sockets, poll_result)
        # close resources gracefully
        sockets.close()

    def check_events(self, sockets, poll_result) -> None:
        """ Forward external Supervisor events to main thread. """
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
            if header == DeferredRequestHeaders.ISOLATE_NODES:
                # isolation request: disconnect the address from subscriber
                sockets.disconnect_subscriber(body)
            else:
                # XML-RPC request
                self.send_request(header, body)

    def send_request(self, header, body) -> None:
        """ Perform the XML-RPC according to the header. """
        if header == DeferredRequestHeaders.CHECK_NODE.value:
            node_name, = body
            self.check_node(node_name)
        elif header == DeferredRequestHeaders.START_PROCESS.value:
            node_name, namespec, extra_args = body
            self.start_process(node_name, namespec, extra_args)
        elif header == DeferredRequestHeaders.STOP_PROCESS.value:
            node_name, namespec = body
            self.stop_process(node_name, namespec)
        elif header == DeferredRequestHeaders.RESTART.value:
            node_name, = body
            self.restart(node_name)
        elif header == DeferredRequestHeaders.SHUTDOWN.value:
            node_name, = body
            self.shutdown(node_name)
        elif header == DeferredRequestHeaders.RESTART_ALL.value:
            node_name, = body
            self.restart_all(node_name)
        elif header == DeferredRequestHeaders.SHUTDOWN_ALL.value:
            node_name, = body
            self.shutdown_all(node_name)

    def check_node(self, node_name: str) -> None:
        """ Check isolation and get all process info asynchronously. """
        try:
            supvisors_rpc = getRPCInterface(node_name, self.env).supvisors
            # get remote perception of master node and state
            master_node_name = supvisors_rpc.get_master_address()
            supvisors_state = supvisors_rpc.get_supvisors_state()
            # check authorization
            status = supvisors_rpc.get_address_info(self.supvisors.address_mapper.local_node_name)
            authorized = AddressStates(status['statecode']) not in [AddressStates.ISOLATING, AddressStates.ISOLATED]
            # get process info if authorized
            if authorized:
                # get information about all processes handled by Supervisor
                all_info = supvisors_rpc.get_all_local_process_info()
                # post to local Supvisors
                self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_INFO, json.dumps((node_name, all_info)))
            # inform local Supvisors that authorization is available
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH,
                                        'node_name:{} authorized:{} master_node_name:{} supvisors_state:{}'
                                        .format(node_name, authorized, master_node_name, supvisors_state['statename']))
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to check address {}'.format(node_name), file=stderr)

    def start_process(self, node_name: str, namespec: str, extra_args: str) -> None:
        """ Start process asynchronously. """
        try:
            proxy = getRPCInterface(node_name, self.env)
            proxy.supvisors.start_args(namespec, extra_args, False)
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to start process {} on {} with extra_args="{}"'
                  .format(namespec, node_name, extra_args), file=stderr)

    def stop_process(self, node_name: str, namespec: str) -> None:
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(node_name, self.env)
            proxy.supervisor.stopProcess(namespec, False)
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to stop process {} on {}'.format(namespec, node_name), file=stderr)

    def restart(self, node_name: str) -> None:
        """ Restart a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(node_name, self.env)
            proxy.supervisor.restart()
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to restart node {}'.format(node_name), file=stderr)

    def shutdown(self, node_name: str) -> None:
        """ Shutdown a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(node_name, self.env)
            proxy.supervisor.shutdown()
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to shutdown node {}'.format(node_name), file=stderr)

    def restart_all(self, node_name: str) -> None:
        """ Ask the Supvisors Master to restart Supvisors. """
        try:
            proxy = getRPCInterface(node_name, self.env)
            proxy.supvisors.restart()
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to send Supvisors restart to Master {}'.format(node_name), file=stderr)

    def shutdown_all(self, node_name: str) -> None:
        """ Ask the Supvisors Master to shutdown Supvisors. """
        try:
            proxy = getRPCInterface(node_name, self.env)
            proxy.supvisors.shutdown()
        except SupvisorsMainLoop.RpcExceptions:
            print('[ERROR] failed to send Supvisors shutdown to Master {}'.format(node_name), file=stderr)

    def send_remote_comm_event(self, event_type: str, event_data) -> None:
        """ Shortcut for the use of sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(event_type, event_data)
        except SupvisorsMainLoop.RpcExceptions:
            # expected on restart / shutdown
            print('[WARN] failed to send event to Supervisor: {} - {}'.format(event_type, event_data), file=stderr)
