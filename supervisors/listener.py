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
from supervisors.options import options
from supervisors.process import stringToProcessStates
from supervisors.utils import TickHeader, ProcessHeader

from supervisor.datatypes import boolean, integer
from supervisor import events

import time, xmlrpclib, zmq

# class for ZMQ publication of event
class _EventPublisher(object):
    def __init__(self, zmqContext):
        self.socket = zmqContext.socket(zmq.PUB)
        # FIXME event port in supervisors
        url = 'tcp://*:{}'.format(options.internalport)
        options.logger.info('binding EventPublisher to %s' % url)
        self.socket.bind(url)

    def sendTickEvent(self, payload):
        # publish ZMQ tick
        options.logger.debug('send TickEvent {}'.format(payload))
        self.socket.send_string(TickHeader, zmq.SNDMORE)
        self.socket.send_pyobj((addressMapper.localAddresses, payload))

    def sendProcessEvent(self, payload):
        # publish ZMQ process state
        options.logger.debug('send ProcessEvent {}'.format(payload))
        self.socket.send_string(ProcessHeader, zmq.SNDMORE)
        self.socket.send_pyobj((addressMapper.localAddresses, payload))


# class for listening Supervisor events
class SupervisorListener(object):
    def __init__(self, zmqContext):
        self.eventPublisher = _EventPublisher(zmqContext)
        # subscribe to internal events
        events.subscribe(events.SupervisorRunningEvent, self._runningListener)
        events.subscribe(events.ProcessStateEvent, self._processListener)
        events.subscribe(events.Tick5Event, self._tickListener)

    def _runningListener(self, event):
        # Supervisor is RUNNING: start Supervisors in this supervisord
        from supervisors.infosource import infoSource
        options.logger.info('send request to local supervisord to start Supervisors')
        try:
            infoSource.source.getSupervisorsRpcInterface().internalStart()
        except xmlrpclib.Fault, why:
            options.logger.critical('failed to start Supervisors: {}'.format(why))

    def _processListener(self, event):
        eventName = events.getEventNameByType(event.__class__)
        options.logger.debug('got Process event from supervisord: {}  {}'.format(eventName, event))
        # create payload to get data
        from supervisor.childutils import get_headers
        payload = get_headers(str(event))
        # additional information
        payload['state'] = stringToProcessStates(eventName.split('_')[-1])
        payload['now'] = int(time.time())
        # convert strings into real values
        payload['from_state'] = stringToProcessStates(payload['from_state'])
        if 'tries' in payload: payload['tries'] = integer(payload['tries'])
        if 'pid' in payload: payload['pid'] = integer(payload['pid'])
        if 'expected' in payload: payload['expected'] = boolean(payload['expected'])
        self.eventPublisher.sendProcessEvent(payload)

    def _tickListener(self, event):
        options.logger.debug('got Tick event from supervisord: {}'.format(event))
        self.eventPublisher.sendTickEvent(event.when)
