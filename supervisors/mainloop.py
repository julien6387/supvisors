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
from supervisors.infosource import infoSource
from supervisors.options import listenerOptions, mainOptions as opt

import zmq, time, threading

# class for subscription to Listener events
class EventSubscriber(object):
    def __init__(self, zmqContext):
        self._socket = zmqContext.socket(zmq.SUB)
        # connect all EventPublisher to Supervisors addresses
        for address in addressMapper.expectedAddresses:
            url = 'tcp://{}:{}'.format(address, listenerOptions.eventport)
            opt.logger.info('connecting EventSubscriber to %s' % url)
            self._socket.connect(url)
            opt.logger.debug('EventSubscriber connected')
        self._socket.setsockopt(zmq.SUBSCRIBE, '')
 
    def receive(self):
        return (self._socket.recv_string(), self._socket.recv_pyobj())

    @property
    def socket(self): return self._socket


# class for Supervisors main loop. all inputs are sequenced here
class SupervisorsMainLoop(threading.Thread):
    def __init__(self):
        # thread attributes
        threading.Thread.__init__(self)
        # ZMQ context definition
        self._zmqContext = zmq.Context.instance()
        self._zmqContext.setsockopt(zmq.LINGER, 0)

    # main loop
    def run(self):
        from supervisors.authorizer import autoFence, Authorizer, authRequester
        from supervisors.context import context
        from supervisors.datahandlers import remotesHandler
        from supervisors.remote import RemoteStates
        from supervisors.utils import TickHeader, ProcessHeader
        from supervisor.states import SupervisorStates, getSupervisorStateDescription
        # create subscription task
        eventSubscriber = EventSubscriber(self._zmqContext)
        # create poller
        poller = zmq.Poller()
        # register event publisher
        poller.register(eventSubscriber.socket, zmq.POLLIN)
        # register auto-fencing sockets
        if autoFence():
            # register authorizer
            self.authorizer = Authorizer(self._zmqContext)
            poller.register(self.authorizer.socket, zmq.POLLIN)
            # register requesters
            authRequester.connect(self._zmqContext)
            authRequester.register(poller)
        timerEventTime = time.time()
        # poll events
        while infoSource.source.supervisord.options.mood == SupervisorStates.RUNNING:
            socks = dict(poller.poll(1000))
            # check tick and process events
            if eventSubscriber.socket in socks and socks[eventSubscriber.socket] == zmq.POLLIN:
                opt.logger.blather('got message on eventSubscriber')
                message = eventSubscriber.receive()
                if message[0] == TickHeader:
                    opt.logger.blather('got tick message: {}'.format(message[1]))
                    context.onTickEvent(message[1][0], message[1][1])
                elif message[0] == ProcessHeader:
                    opt.logger.blather('got process message: {}'.format(message[1]))
                    context.onProcessEvent(message[1][0], message[1][1])
            # auth / fencing job
            if autoFence():
                # check authorization responses
                address = authRequester.checkPoller(socks)
                if address is not None:
                    authorized = authRequester.recvResponse(address)
                    opt.logger.warn('got auth response from %s' % address)
                    context.onAuthorization(address, authorized)
                # check authorization requests
                if self.authorizer.socket in socks and socks[self.authorizer.socket] == zmq.POLLIN:
                    opt.logger.blather('got message on authorizer')
                    dealer = self.authorizer.recvRequest()
                    opt.logger.warn('got auth request from {}'.format(dealer))
                    # check if board state is ISOLATED
                    remoteAddress = addressMapper.getExpectedAddress([dealer])
                    permit = remoteAddress and remotesHandler.getRemoteInfo(remoteAddress).state != RemoteStates.ISOLATED
                    self.authorizer.sendResponse(dealer, permit)
            # check periodic task
            if timerEventTime + 5 < time.time():
                opt.logger.blather('got message on timerSocket')
                context.onTimerEvent()
                timerEventTime = time.time()
            # an application that wants process events may use its own EventSubscriber but it's in python
            # TODO: or publish from here using thrift /protobuf / msgpack ?
        opt.logger.info('exiting main loop because SupervisorState={}'.format(getSupervisorStateDescription(infoSource.source.supervisord.options.mood)))
        # close zmq sockets
        eventSubscriber.socket.close()
        if autoFence():
            authRequester.close()
            self.authorizer.socket.close()
        # close zmq context
        self._zmqContext.term()
        # cleanup in case of restarting
        context.cleanup()
        # finally, close logger
        opt.logger.close()
