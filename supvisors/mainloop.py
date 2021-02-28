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
import zmq

from threading import Event, Thread
from typing import Any
from sys import stderr

from supvisors.rpcrequests import getRPCInterface
from supvisors.supvisorszmq import SupvisorsZmq
from supvisors.ttypes import AddressStates
from supvisors.utils import DeferredRequestHeaders, RemoteCommEvents


class SupvisorsMainLoop(Thread):
    """ Class for Supvisors main loop. All inputs are sequenced here.
    The Supervisor logger is not thread-safe so do NOT use it here.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - stop_event: the event used to stop the thread,
        - env: the environment variables linked to Supervisor security access,
        - proxy: the proxy to the internal RPC interface.
    """

    def __init__(self, supvisors: Any) -> None:
        """ Initialization of the attributes. """
        # thread attributes
        Thread.__init__(self)
        # create stop event
        self.stop_event = Event()
        # keep a reference to the Supvisors instance and to the environment
        self.supvisors = supvisors
        self.env = supvisors.info_source.get_env()
        # create a XML-RPC client to the local Supervisor instance
        self.proxy = getRPCInterface('localhost', self.env)

    def stopping(self):
        """ Access to the loop attribute (used to drive tests on run method). """
        return self.stop_event.is_set()

    def stop(self):
        """ Request to stop the infinite loop by resetting its flag. """
        if self.is_alive():
            self.stop_event.set()
            # the thread cannot be blocked in a XML-RPC call because of the
            # close_httpservers called just before this stop
            # so join is expected to end properly
            self.join()

    def run(self):
        """ Contents of the infinite loop. """
        # Create zmq sockets
        sockets = SupvisorsZmq(self.supvisors)
        # create poller
        poller = zmq.Poller()
        # register sockets
        poller.register(sockets.internal_subscriber.socket, zmq.POLLIN)
        poller.register(sockets.puller.socket, zmq.POLLIN)
        # poll events forever
        while not self.stopping():
            socks = dict(poller.poll(500))
            # test stop condition again: if Supervisor is stopping,
            # any XML-RPC call would block this thread, and the other
            # because of the join
            if not self.stopping():
                self.check_requests(sockets, socks)
                self.check_events(sockets.internal_subscriber, socks)
        # close resources gracefully
        poller.unregister(sockets.puller.socket)
        poller.unregister(sockets.internal_subscriber.socket)
        sockets.close()

    def check_events(self, subscriber, socks):
        """ Forward external Supervisor events to main thread. """
        if subscriber.socket in socks and socks[subscriber.socket] == zmq.POLLIN:
            try:
                message = subscriber.receive()
            except:
                print('[ERROR] failed to get data from subscriber', file=stderr)
            else:
                # The events received are not processed directly in this thread because it would conflict
                # with the processing in the Supervisor thread, as they use the same data.
                # That's why a RemoteCommunicationEvent is used to push the event in the Supervisor thread.
                self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_EVENT, json.dumps(message))

    def check_requests(self, zmq_sockets, socks):
        """ Defer internal requests. """
        if zmq_sockets.puller.socket in socks and socks[zmq_sockets.puller.socket] == zmq.POLLIN:
            try:
                header, body = zmq_sockets.puller.receive()
            except:
                print('[ERROR] failed to get data from puller', file=stderr)
            else:
                if header == DeferredRequestHeaders.ISOLATE_ADDRESSES:
                    # isolation request: disconnect the address from subscriber
                    zmq_sockets.internal_subscriber.disconnect(body)
                else:
                    # XML-RPC request
                    self.send_request(header, body)

    def send_request(self, header, body):
        """ Perform the XML-RPC according to the header. """
        if header == DeferredRequestHeaders.CHECK_ADDRESS:
            address_name, = body
            self.check_address(address_name)
        elif header == DeferredRequestHeaders.START_PROCESS:
            address_name, namespec, extra_args = body
            self.start_process(address_name, namespec, extra_args)
        elif header == DeferredRequestHeaders.STOP_PROCESS:
            address_name, namespec = body
            self.stop_process(address_name, namespec)
        elif header == DeferredRequestHeaders.RESTART:
            address_name, = body
            self.restart(address_name)
        elif header == DeferredRequestHeaders.SHUTDOWN:
            address_name, = body
            self.shutdown(address_name)

    def check_address(self, address_name):
        """ Check isolation and get all process info asynchronously. """
        try:
            remote_proxy = getRPCInterface(address_name, self.env)
            # get remote perception of master node
            master_address = remote_proxy.supvisors.get_master_address()
            # check authorization
            status = remote_proxy.supvisors.get_address_info(address_name)
            authorized = status['statecode'] not in [AddressStates.ISOLATING, AddressStates.ISOLATED]
            # get process info if authorized
            if authorized:
                # get information about all processes handled by Supervisor
                all_info = remote_proxy.supvisors.get_all_local_process_info()
                # post internally
                self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_INFO,
                                            json.dumps((address_name, all_info)))
            # inform local Supvisors that authorization is available
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH,
                                        'address_name:{} authorized:{} master_address:{}'
                                        .format(address_name, authorized, master_address))
        except:
            print('[ERROR] failed to check address {}'.format(address_name), file=stderr)

    def start_process(self, address_name, namespec, extra_args):
        """ Start process asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supvisors.start_args(namespec, extra_args, False)
        except:
            print('[ERROR] failed to start process {} on {} with extra_args="{}"'
                  .format(namespec, address_name, extra_args), file=stderr)

    def stop_process(self, address_name, namespec):
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supervisor.stopProcess(namespec, False)
        except:
            print('[ERROR] failed to stop process {} on {}'.format(namespec, address_name),
                  file=stderr)

    def restart(self, address_name):
        """ Restart a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supervisor.restart()
        except:
            print('[ERROR] failed to restart address {}'.format(address_name), file=stderr)

    def shutdown(self, address_name):
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supervisor.shutdown()
        except:
            print('[ERROR] failed to shutdown address {}'.format(address_name), file=stderr)

    def send_remote_comm_event(self, event_type, event_data):
        """ Shortcut for the use of sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(event_type, event_data)
        except:
            # expected on restart / shutdown
            print('[WARN] failed to send event to Supervisor: {}'.format(event_type), file=stderr)
