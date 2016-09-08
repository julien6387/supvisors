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

import zmq

from supervisors.utils import *


# class for ZMQ publication of event
class _EventPublisher(object):

    def __init__(self, supervisors):
        self.supervisors = supervisors
        self.socket = None

    def open(self, zmqContext):
        self.socket = zmqContext.socket(zmq.PUB)
        # WARN: this is a local binding, only visible to processes located on the same address
        url = 'tcp://127.0.0.1:{}'.format(self.supervisors.options.eventPort)
        self.supervisors.logger.info('binding local Supervisors EventPublisher to %s' % url)
        self.socket.bind(url)

    def close(self):
        if not self.socket: return
        self.socket.close()
        self.socket = None

    def sendSupervisorsStatus(self, status):
        if not self.socket: return
        self.supervisors.logger.debug('send SupervisorsStatus {}'.format(status))
        self.socket.send_string(SupervisorsStatusHeader, zmq.SNDMORE)
        self.socket.send_json(status.toJSON())

    def sendRemoteStatus(self, status):
        if not self.socket: return
        self.supervisors.logger.debug('send RemoteStatus( {}'.format(status))
        self.socket.send_string(RemoteStatusHeader, zmq.SNDMORE)
        self.socket.send_json(status.toJSON())

    def sendApplicationStatus(self, status):
        if not self.socket: return
        self.supervisors.logger.debug('send ApplicationStatus {}'.format(status))
        self.socket.send_string(ApplicationStatusHeader, zmq.SNDMORE)
        self.socket.send_json(status.toJSON())

    def sendProcessStatus(self, status):
        if not self.socket: return
        self.supervisors.logger.debug('send ProcessStatus {}'.format(status))
        self.socket.send_string(ProcessStatusHeader, zmq.SNDMORE)
        self.socket.send_json(status.toJSON())

    def sendStatistics(self, stats):
        if not self.socket: return
        self.supervisors.logger.debug('send Statistics {}'.format(stats))
        self.socket.send_string(StatisticsHeader, zmq.SNDMORE)
        self.socket.send_json(status.toJSON())
