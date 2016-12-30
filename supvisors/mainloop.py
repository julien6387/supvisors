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

import time
import zmq

from Queue import Empty, Queue
from threading import Thread

from supvisors.rpcrequests import getRPCInterface
from supvisors.utils import (supvisors_short_cuts,
    SUPVISORS_EVENT, SUPVISORS_TASK)

class EventSubscriber(object):
    """ Class for subscription to Listener events.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - socket: the PyZMQ subscriber.
    """

    def __init__(self, supvisors, zmq_context):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.socket = zmq_context.socket(zmq.SUB)
        # connect all EventPublisher to Supvisors addresses
        for address in supvisors.address_mapper.addresses:
            url = 'tcp://{}:{}'.format(address, supvisors.options.internal_port)
            supvisors.logger.info('connecting EventSubscriber to %s' % url)
            self.socket.connect(url)
        supvisors.logger.debug('EventSubscriber connected')
        self.socket.setsockopt(zmq.SUBSCRIBE, '')
 
    def receive(self):
        """ Reception and pyobj unserialization of one message including:
        - the message header,
        - the origin,
        - the body of the message. """
        return self.socket.recv_pyobj()

    def disconnect(self, addresses):
        """ This method disconnects from the PyZMQ socket all addresses passed in parameter. """
        for address in addresses:
            url = 'tcp://{}:{}'.format(address, self.supvisors.options.internal_port)
            self.supvisors.logger.info('disconnecting EventSubscriber from %s' % url)
            self.socket.disconnect(url)

    def close(self):
        """ This method closes the PyZMQ socket. """
        self.socket.close()


class SupvisorsMainLoop(Thread):
    """ Class for Supvisors main loop. All inputs are sequenced here.

    Attributes:
        - supvisors: a reference to the Supvisors context,
        - zmq_context: the ZeroMQ context used to create sockets,
        - subscriber: the event subscriber,
        - loop: the infinite loop flag.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # thread attributes
        Thread.__init__(self)
        # shortcuts
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['info_source', 'logger'])
        # create queues for internal communication
        self.event_queue = Queue()
        self.address_queue = Queue()
        # ZMQ context definition
        self.zmq_context = zmq.Context()
        self.zmq_context.setsockopt(zmq.LINGER, 0)
        # create event socket
        self.subscriber = EventSubscriber(supvisors, self.zmq_context)

    def close(self):
        """ This method closes the resources. """
        # close the event socket
        self.subscriber.close()
        # close ZMQ context
        self.zmq_context.term()

    def stop(self):
        """ Request to stop the infinite loop by resetting its flag. """
        self.logger.info('request to stop main loop')
        self.loop = False

    # main loop
    def run(self):
        """ Contents of the infinite loop.
        Do NOT use logger here. """
        # create a xml-rpc client to the local Supervisor instance
        proxy = getRPCInterface('localhost', self.info_source.get_env())
        # create poller
        poller = zmq.Poller()
        # register event subscriber
        poller.register(self.subscriber.socket, zmq.POLLIN) 
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
                        # That's why they are pushed into a Queue and Supvisors uses a RemoteCommunicationEvent
                        # to process the event in the Supervisor thread.
                        self.event_queue.put_nowait(message)
                        try:
                            proxy.supervisor.sendRemoteCommEvent(SUPVISORS_EVENT, '')
                        except:
                            # can happen on restart / shutdown. nothing left to do
                            pass
                # check periodic task
                if timer_event_time + 5 < time.time():
                    try:
                        proxy.supervisor.sendRemoteCommEvent(SUPVISORS_TASK, '')
                    except:
                        # can happen on restart / shutdown. nothing left to do
                        pass
                    # set date for next task
                    timer_event_time = time.time()
                # check isolation of addresses
                try:
                    addresses = self.address_queue.get_nowait()
                except Empty:
                    # nothing to do
                    pass
                else:
                    # disconnect isolated addresses from sockets
                    self.subscriber.disconnect(addresses)
        # close resources gracefully
        poller.unregister(self.subscriber.socket)
        self.close()
