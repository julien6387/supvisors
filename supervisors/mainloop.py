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

import threading
import time
import zmq

from Queue import Empty, PriorityQueue, Queue

from supervisors.utils import (EventHeaders, SUPERVISORS_EVENT, 
    SUPERVISORS_TASK, supervisors_short_cuts)


class EventSubscriber(object):
    """ Class for subscription to Listener events.

    Attributes:
    - supervisors: a reference to the Supervisors context,
    - socket: the PyZMQ subscriber. """

    def __init__(self, supervisors, zmq_context):
        """ Initialization of the attributes. """
        self.supervisors = supervisors
        self.socket = zmq_context.socket(zmq.SUB)
        # connect all EventPublisher to Supervisors addresses
        for address in supervisors.address_mapper.addresses:
            url = 'tcp://{}:{}'.format(address, supervisors.options.internal_port)
            supervisors.logger.info('connecting EventSubscriber to %s' % url)
            self.socket.connect(url)
        supervisors.logger.debug('EventSubscriber connected')
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
            url = 'tcp://{}:{}'.format(address, self.supervisors.options.internal_port)
            self.supervisors.logger.info('disconnecting EventSubscriber from %s' % url)
            self.socket.disconnect(url)

    def close(self):
        """ This method closes the PyZMQ socket. """
        self.socket.close()


class SupervisorsMainLoop(threading.Thread):
    """ Class for Supervisors main loop. All inputs are sequenced here.

    Attributes:
    - supervisors: a reference to the Supervisors context,
    - zmq_context: the ZeroMQ context used to create sockets,
    - subscriber: the event subscriber,
    - loop: the infinite loop flag. """

    def __init__(self, supervisors):
        """ Initialization of the attributes. """
        # thread attributes
        threading.Thread.__init__(self)
        # shortcuts
        self.supervisors = supervisors
        supervisors_short_cuts(self, ['fsm', 'logger', 'statistician'])
        # create queues for internal comminucation
        self.event_queue = PriorityQueue()
        self.address_queue = Queue()
        # ZMQ context definition
        self.zmq_context = zmq.Context.instance()
        self.zmq_context.setsockopt(zmq.LINGER, 0)
        # create event sockets
        self.subscriber = EventSubscriber(supervisors, self.zmq_context)
        supervisors.publisher.open(self.zmq_context)

    def close(self):
        """ This method closes the resources. """
        # close the ZeroMQ sockets
        self.supervisors.publisher.close()
        self.subscriber.close()
        # close zmq context
        self.zmq_context.term()
        # finally, close logger
        self.logger.close()

    def stop(self):
        """ Request to stop the infinite loop by resetting its flag. """
        self.logger.info('request to stop main loop')
        self.loop = False

    # main loop
    def run(self):
        """ Contents of the infinite loop. """
        # create poller
        poller = zmq.Poller()
        # register event subscriber
        poller.register(self.subscriber.socket, zmq.POLLIN) 
        timer_event_time = time.time()
        # get the proxy of the local Supervisor for XML-RPC
        client, supervisor = self.supervisors.requester.supervisor_proxy("localhost")
        # poll events every seconds
        self.loop = True
        while self.loop:
            socks = dict(poller.poll(1000))
            # Need to test loop flag again as its value may have changed in the last second.
            # WARN: there is a risk of deadlock when shutdown is called by XML-RPC.
            # Upon reception of the SupervisorStoppingEvent, the loop flag is set to False
            # and the listener waits for this thread to end.
            # Unfortunately, there is a chance that the flag is set between the test of the
            # flag and the use of sendRemoteCommEvent, leading to a deadlock in RPC calls.
            # A timeout has been set on the thread join to avoid the deadlock.
            if self.loop:
                # check tick and process events
                if self.subscriber.socket in socks and socks[self.subscriber.socket] == zmq.POLLIN:
                    self.logger.blather('got message on event subscriber')
                    try:
                        message = self.subscriber.receive()
                    except Exception, e:
                        self.logger.warn('failed to get data from subscriber: {}'.format(e.message))
                    else:
                        # The events received are not processed directly in this thread because it may conflict
                        # with the Supervisors functions triggered from the Supervisor thread, as they use the
                        # same data. So they are pushed into a PriorityQueue (Tick > Process > Statistics) and
                        # Supervisors uses a RemoteCommunicationEvent to unstack and process the event from
                        # the context of the Supervisor thread.
                        self.event_queue.put_nowait(message)
                        if self.loop:
                            supervisor.sendRemoteCommEvent(SUPERVISORS_EVENT, '')
                # check periodic task
                if timer_event_time + 5 < time.time():
                    if self.loop:
                        supervisor.sendRemoteCommEvent(SUPERVISORS_TASK, '')
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
        self.logger.info('exiting main loop')
        self.close()

    def unstack_event(self):
        """ Unstack and process one event from the PriorityQueue. """
        event_type, event_address, event_data = self.event_queue.get_nowait()
        if event_type == EventHeaders.TICK:
            self.logger.blather('got tick message from {}: {}'.format(event_address, event_data))
            self.fsm.on_tick_event(event_address, event_data)
        elif event_type == EventHeaders.PROCESS:
            self.logger.blather('got process message from {}: {}'.format(event_address, event_data))
            self.fsm.on_process_event(event_address, event_data)
        elif event_type == EventHeaders.STATISTICS:
            self.logger.blather('got statistics message from {}: {}'.format(event_address, event_data))
            self.statistician.push_statistics(event_address, event_data)

    def periodic_task(self):
        """ Periodic task that mainly checks that addresses are still operating. """
        self.logger.blather('periodic task')
        addresses = self.fsm.on_timer_event()
        # pushes isolated addresses to main loop
        self.address_queue.put_nowait(addresses)

