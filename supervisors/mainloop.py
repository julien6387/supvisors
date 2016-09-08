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

from supervisors.addressmapper import addressMapper
from supervisors.options import options
from supervisors.publisher import eventPublisher
from supervisors.statemachine import fsm
from supervisors.statistics import statisticsCompiler
from supervisors.utils import TickHeader, ProcessHeader, StatisticsHeader


# class for subscription to Listener events
class EventSubscriber(object):
    def __init__(self, zmqContext):
        self.socket = zmqContext.socket(zmq.SUB)
        # connect all EventPublisher to Supervisors addresses
        for address in addressMapper.addresses:
            url = 'tcp://{}:{}'.format(address, options.internalPort)
            options.logger.info('connecting EventSubscriber to %s' % url)
            self.socket.connect(url)
        options.logger.debug('EventSubscriber connected')
        self.socket.setsockopt(zmq.SUBSCRIBE, '')
 
    def receive(self):
        return (self.socket.recv_string(), self.socket.recv_pyobj())

    def disconnect(self, addresses):
        for address in addresses:
            url = 'tcp://{}:{}'.format(address, options.internalPort)
            options.logger.info('disconnecting EventSubscriber from %s' % url)
            self.socket.disconnect(url)

    def close(self):
        self.socket.close()


# class for Supervisors main loop. all inputs are sequenced here
class SupervisorsMainLoop(threading.Thread):
    def __init__(self, zmqContext):
        # thread attributes
        threading.Thread.__init__(self)
        # create event sockets
        self.eventSubscriber = EventSubscriber(zmqContext)
        eventPublisher.open(zmqContext)
        # configure statistics compiler
        statisticsCompiler.clearAll(options.statsPeriods, options.statsHisto)

    def stop(self):
        options.logger.info('request to stop main loop')
        self.loop = False

    # main loop
    def run(self):
        # create poller
        poller = zmq.Poller()
        # register event publisher
        poller.register(self.eventSubscriber.socket, zmq.POLLIN) 
        self.timerEventTime = time.time()
        # poll events every seconds
        self.loop = True
        while self.loop:
            socks = dict(poller.poll(1000))
            # check tick and process events
            if self.eventSubscriber.socket in socks and socks[self.eventSubscriber.socket] == zmq.POLLIN:
                options.logger.blather('got message on eventSubscriber')
                try:
                    message = self.eventSubscriber.receive()
                except Exception, e:
                    options.logger.warn('failed to get data from subscriber: {}'.format(e.message))
                else:
                    if message[0] == TickHeader:
                        options.logger.blather('got tick message: {}'.format(message[1]))
                        fsm.onTickEvent(message[1][0], message[1][1])
                    elif message[0] == ProcessHeader:
                        options.logger.blather('got process message: {}'.format(message[1]))
                        fsm.onProcessEvent(message[1][0], message[1][1])
                    elif message[0] == StatisticsHeader:
                        options.logger.blather('got statistics message: {}'.format(message[1]))
                        statisticsCompiler.pushStatistics(message[1][0], message[1][1])
            # check periodic task
            if self.timerEventTime + 5 < time.time():
                self._doPeriodicTask()
            # publish all events from here using pyzmq json
        options.logger.info('exiting main loop')
        self._close()

    def _doPeriodicTask(self):
        options.logger.blather('periodic task')
        addresses = fsm.onTimerEvent()
        # disconnect isolated addresses from sockets
        self.eventSubscriber.disconnect(addresses)
        # set date for next task
        self.timerEventTime = time.time()

    def _close(self):
        # close zmq sockets
        eventPublisher.close()
        self.eventSubscriber.close()

