#!/usr/bin/python
#-*- coding: utf-8 -*-

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
import zmq

from threading import Thread

from supvisors.rpcrequests import getRPCInterface
from supvisors.ttypes import AddressStates
from supvisors.utils import (supvisors_short_cuts, RequestHeaders, RemoteCommEvents)


class SupvisorsMainLoop(Thread):
    """ Class for Supvisors main loop. All inputs are sequenced here.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - subscriber: a reference to the internal event subscriber,
        - loop: the infinite loop flag.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # thread attributes
        Thread.__init__(self)
        # shortcuts
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['info_source', 'logger'])
        # keep a reference of zmq sockets
        self.subscriber = supvisors.zmq.internal_subscriber
        self.puller = supvisors.zmq.puller
        # keep a reference to the environment
        self.env = self.info_source.get_env()
        # create a xml-rpc client to the local Supervisor instance
        self.proxy = getRPCInterface('localhost', self.env)

    def stop(self):
        """ Request to stop the infinite loop by resetting its flag. """
        self.logger.info('request to stop main loop')
        self.loop = False
        self.join()

    # main loop
    def run(self):
        """ Contents of the infinite loop.
        Do NOT use logger here. """
        # create poller
        poller = zmq.Poller()
        # register sockets
        poller.register(self.subscriber.socket, zmq.POLLIN) 
        poller.register(self.puller.socket, zmq.POLLIN) 
        timer_event_time = time.time()
        # poll events every seconds
        self.loop = True
        while self.loop:
            socks = dict(poller.poll(500))
            # Need to test loop flag again as its value may have changed in the last second.
            if self.loop:
                # check tick and process events
                if self.subscriber.socket in socks and socks[self.subscriber.socket] == zmq.POLLIN:
                    try:
                        message = self.subscriber.receive()
                    except:
                        # failed to get data from subscriber
                        pass
                    else:
                        # The events received are not processed directly in this thread because it may conflict with
                        # the Supvisors functions triggered from the Supervisor thread, as they use the same data.
                        # That's why a RemoteCommunicationEvent is used to process the event in the Supervisor thread.
                        self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_EVENT, json.dumps(message))
                # check xml-rpc requests
                if self.puller.socket in socks and socks[self.puller.socket] == zmq.POLLIN:
                    try:
                        header, body = self.puller.receive()
                    except:
                        # failed to get data from subscriber
                        pass
                    else:
                        self.send_request(header, body)
                # check periodic task
                if timer_event_time + 5 < time.time():
                    self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_TASK, '')
                    # set date for next task
                    timer_event_time = time.time()
        # close resources gracefully
        self.logger.info('end of main loop')
        poller.unregister(self.subscriber.socket)

    def send_request(self, header, body):
        """ Perform the XML-RPC according to the header. """
        if header == RequestHeaders.DEF_CHECK_ADDRESS:
            address_name, = body
            self.check_address(address_name)
        elif header == RequestHeaders.DEF_ISOLATE_ADDRESSES:
            self.subscriber.disconnect(body)
        elif header == RequestHeaders.DEF_START_PROCESS:
            address_name, namespec, extra_args = body
            self.start_process(address_name, namespec, extra_args)
        elif header == RequestHeaders.DEF_STOP_PROCESS:
            address_name, namespec = body
            self.stop_process(address_name, namespec)
        elif header == RequestHeaders.DEF_RESTART:
            address_name, = body
            self.restart(address_name)
        elif header == RequestHeaders.DEF_SHUTDOWN:
            address_name, = body
            self.shutdown(address_name)

    def check_address(self, address_name):
        """ Check isolation and get all process info asynchronously. """
        try:
            remote_proxy = getRPCInterface(address_name, self.env)
            # check authorization
            status = remote_proxy.supvisors.get_address_info(address_name)
            authorized = status['statecode'] not in [AddressStates.ISOLATING, AddressStates.ISOLATED]
            # get process info if authorized
            if authorized:
                all_info = remote_proxy.supervisor.getAllProcessInfo()
                self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_INFO, json.dumps((address_name, all_info)))
            # inform local Supvisors that authorization is available
            self.send_remote_comm_event(RemoteCommEvents.SUPVISORS_AUTH, 'address_name:{} authorized:{}'.format(address_name, authorized))
        except:
            self.logger.error('failed to check address {}'.format(address_name))

    def start_process(self, address_name, namespec, extra_args):
        """ Start process asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supvisors.start_args(namespec, extra_args, False)
        except:
            self.logger.error('failed to start process {} on {} with {}'.format(namespec, address_name, extra_args))

    def stop_process(self, address_name, namespec):
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supervisor.stopProcess(namespec, False)
        except:
            self.logger.error('failed to stop process {} on {}'.format(namespec, address_name))

    def restart(self, address_name):
        """ Restart a Supervisor instance asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supervisor.restart()
        except:
            self.logger.error('failed to restart address {}'.format(address_name))

    def shutdown(self, address_name):
        """ Stop process asynchronously. """
        try:
            proxy = getRPCInterface(address_name, self.env)
            proxy.supervisor.shutdown()
        except:
            self.logger.error('failed to shutdown address {}'.format(address_name))

    def send_remote_comm_event(self, event_type, event_data):
        """ Shortcut for the use of sendRemoteCommEvent. """
        try:
            self.proxy.supervisor.sendRemoteCommEvent(event_type, event_data)
        except:
            # can happen on restart / shutdown
            # nothing left to do about that
            pass
