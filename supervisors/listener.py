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
from supervisors.infosource import infoSource, ASource
from supervisors.options import listenerOptions as opt
from supervisors.process import stringToProcessStates
from supervisors.utils import TickHeader, ProcessHeader

from supervisor.childutils import listener, get_headers
from supervisor.datatypes import boolean
from supervisor.events import SupervisorRunningEvent, TickEvent, ProcessStateEvent, EventTypes

import os, time, xmlrpclib, zmq

# Listener is spawned by Supervisor so information is available in environment
class _EnvironmentSource(ASource):
    # used environment variables set by Supervisor
    ServerUrl = 'SUPERVISOR_SERVER_URL'
    UserName = 'SUPERVISOR_USERNAME'
    Password = 'SUPERVISOR_PASSWORD'

    def __init__(self):
        self._serverUrl = self._getSupervisorEnv(self.ServerUrl)
        # MUST be http, not unix
        if not self._serverUrl.startswith('http'):
            raise Exception('wrong SUPERVISOR_SERVER_URL (HTTP expected): {}'.format(self._serverUrl))
        self._serverPort = self._getUrlPort() if self._serverUrl else None
        self._userName = self._getSupervisorEnv(self.UserName)
        self._password = self._getSupervisorEnv(self.Password)

    def getServerUrl(self): return self._serverUrl
    def getServerPort(self): return self._serverPort
    def getUserName(self): return self._userName
    def getPassword(self): return self._password

    def _getSupervisorEnv(self,  envname):
        try:
            value = os.environ[envname]
        except KeyError:
            opt.logger.error('{} not found in environment'.format(envname))
            return ''
        else:
            opt.logger.debug(envname + '=' + value)
            return value;

    def _getUrlPort(self):
        try:
            return int(self._serverUrl.split(':')[-1]);
        except ValueError:
            opt.logger.error('wrong format for %s' % self._serverUrl)
        return 0


# class for ZMQ publication of event
class _EventPublisher(object):
    def __init__(self):
        context = zmq.Context()
        context.setsockopt(zmq.LINGER, 0)
        self._socket = context.socket(zmq.PUB)
        url = 'tcp://*:{}'.format(opt.eventport)
        opt.logger.info('binding EventPublisher to %s' % url)
        self._socket.bind(url)

    def sendTickEvent(self, payload):
        # publish ZMQ tick
        opt.logger.debug('send TickEvent {}'.format(payload))
        self._socket.send_string(TickHeader, zmq.SNDMORE)
        self._socket.send_pyobj((addressMapper.localAddresses, payload))

    def sendProcessEvent(self, payload):
        # publish ZMQ process state
        opt.logger.debug('send ProcessEvent {}'.format(payload))
        self._socket.send_string(ProcessHeader, zmq.SNDMORE)
        self._socket.send_pyobj((addressMapper.localAddresses, payload))


# class for listening Supervisor events
class _SupervisorListener(object):
    def __init__(self):
        self._eventPublisher = _EventPublisher()
        self._loop = True

    # main loop: killed by TERM signal
    def run(self):
        while self._loop:
            # wait event
            event = listener.wait()
            opt.logger.trace(event[0])
            # get event type
            eventname = event[0]['eventname']
            evType = EventTypes.__dict__[eventname]
            opt.logger.debug(evType)
            # get payload as dict
            payload = get_headers(event[1])
            opt.logger.trace(payload)
            # process event by type
            if issubclass(evType, TickEvent):
                self._tickEvent(payload)
            elif issubclass(evType, ProcessStateEvent):
                self._processEvent(eventname, payload)
            elif issubclass(evType, SupervisorRunningEvent):
                self._supervisorEvent()
            # send result
            listener.ok()

    def _tickEvent(self, payload):
        # convert strings into real values
        payload['when'] = int(payload['when'])
        self._eventPublisher.sendTickEvent(payload)

    def _processEvent(self, eventname, payload):
        # additional information
        payload['state'] = stringToProcessStates(eventname.split('_')[-1])
        payload['now'] = int(time.time())
        # convert strings into real values
        payload['from_state'] = stringToProcessStates(payload['from_state'])
        if 'tries' in payload: payload['tries'] = int(payload['tries'])
        if 'pid' in payload: payload['pid'] = int(payload['pid'])
        if 'expected' in payload: payload['expected'] = boolean(payload['expected'])
        self._eventPublisher.sendProcessEvent(payload)

    def _supervisorEvent(self):
        # Supervisor is RUNNING: start Supervisors
        from supervisors.xmlrpcclient import XmlRpcClient
        opt.logger.info('send request to local supervisord to start Supervisors')
        try:
            XmlRpcClient('localhost').proxy.supervisors.internalStart()
        except xmlrpclib.Fault, why:
            opt.logger.critical('failed to start Supervisors: {}'.format(why))
            self._loop = False


# Listener main
if __name__ == "__main__":
    # read options
    opt.realize(True)
    # configure supervisor info source
    infoSource.source = _EnvironmentSource()
    # start event listener
    supervisorListener = _SupervisorListener()
    supervisorListener.run()
