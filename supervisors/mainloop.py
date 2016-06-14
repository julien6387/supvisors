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

from supervisors.addressmapper import addressMapper
from supervisors.context import context
from supervisors.infosource import infoSource
from supervisors.options import listenerOptions, mainOptions as opt
from supervisors.statemachine import fsm

import zmq, time, threading

# class for subscription to Listener events
class EventSubscriber(object):
    def __init__(self, zmqContext):
        self.socket = zmqContext.socket(zmq.SUB)
        # connect all EventPublisher to Supervisors addresses
        for address in addressMapper.expectedAddresses:
            url = 'tcp://{}:{}'.format(address, listenerOptions.eventport)
            opt.logger.info('connecting EventSubscriber to %s' % url)
            self.socket.connect(url)
        opt.logger.debug('EventSubscriber connected')
        self.socket.setsockopt(zmq.SUBSCRIBE, '')
 
    def receive(self):
        return (self.socket.recv_string(), self.socket.recv_pyobj())

    def disconnect(self, addresses):
        for address in addresses:
            url = 'tcp://{}:{}'.format(address, listenerOptions.eventport)
            opt.logger.info('disconnecting EventSubscriber from %s' % url)
            self.socket.disconnect(url)


# class for Supervisors main loop. all inputs are sequenced here
class SupervisorsMainLoop(threading.Thread):
    def __init__(self):
        # thread attributes
        threading.Thread.__init__(self)
        # ZMQ context definition
        self.zmqContext = zmq.Context.instance()
        self.zmqContext.setsockopt(zmq.LINGER, 0)
        # create sockets
        self.eventSubscriber = EventSubscriber(self.zmqContext)

    # main loop
    def run(self):
        from supervisors.utils import TickHeader, ProcessHeader
        from supervisor.states import SupervisorStates, getSupervisorStateDescription
        # create poller
        poller = zmq.Poller()
        # register event publisher
        poller.register(self.eventSubscriber.socket, zmq.POLLIN) 
        self.timerEventTime = time.time()
        # poll events every seconds
        while infoSource.source.supervisord.options.mood == SupervisorStates.RUNNING:
            socks = dict(poller.poll(1000))
            # check tick and process events
            if self.eventSubscriber.socket in socks and socks[self.eventSubscriber.socket] == zmq.POLLIN:
                opt.logger.blather('got message on eventSubscriber')
                message = self.eventSubscriber.receive()
                if message[0] == TickHeader:
                    opt.logger.blather('got tick message: {}'.format(message[1]))
                    context.onTickEvent(message[1][0], message[1][1])
                elif message[0] == ProcessHeader:
                    opt.logger.blather('got process message: {}'.format(message[1]))
                    context.onProcessEvent(message[1][0], message[1][1])
            # check periodic task
            if self.timerEventTime + 5 < time.time():
                self._doPeriodicTask()
            # an application that wants process events may use its own EventSubscriber but it's in python
            # TODO: or publish from here using thrift /protobuf / msgpack ?
        opt.logger.info('exiting main loop because SupervisorState={}'.format(getSupervisorStateDescription(infoSource.source.supervisord.options.mood)))
        self._close()

    def _doPeriodicTask(self):
        opt.logger.blather('periodic task')
        context.onTimerEvent()
        fsm.next()
        # check if new isolating remotes
        addresses = context.handleIsolation()
        # disconnect isolated addresses from sockets
        self.eventSubscriber.disconnect(addresses)
        # set date for next task
        self.timerEventTime = time.time()

    def _close(self):
        # close zmq sockets
        self.eventSubscriber.socket.close()
         # close zmq context
        self.zmqContext.term()
        # cleanup in case of restarting
        context.restart()
        # finally, close logger
        opt.logger.close()
