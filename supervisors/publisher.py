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
class EventPublisher(object):

    def __init__(self, supervisors):
        self.supervisors = supervisors
        self.socket = None

    def open(self, zmq_context):
        self.socket = zmq_context.socket(zmq.PUB)
        # WARN: this is a local binding, only visible to processes located on the same address
        url = 'tcp://127.0.0.1:{}'.format(self.supervisors.options.event_port)
        self.supervisors.logger.info('binding local Supervisors EventPublisher to %s' % url)
        self.socket.bind(url)

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def send_supervisors_status(self, status):
        if self.socket:
            self.supervisors.logger.debug('send SupervisorsStatus {}'.format(status))
            self.socket.send_string(SUPERVISORS_STATUS_HEADER, zmq.SNDMORE)
            self.socket.send_json(status.to_json())

    def send_address_status(self, status):
        if self.socket:
            self.supervisors.logger.debug('send RemoteStatus {}'.format(status))
            self.socket.send_string(ADDRESS_STATUS_HEADER, zmq.SNDMORE)
            self.socket.send_json(status.to_json())

    def send_application_status(self, status):
        if self.socket:
            self.supervisors.logger.debug('send ApplicationStatus {}'.format(status))
            self.socket.send_string(APPLICATION_STATUS_HEADER, zmq.SNDMORE)
            self.socket.send_json(status.to_json())

    def send_process_status(self, status):
        if self.socket:
            self.supervisors.logger.debug('send ProcessStatus {}'.format(status))
            self.socket.send_string(PROCESS_STATUS_HEADER, zmq.SNDMORE)
            self.socket.send_json(status.to_json())

    def send_statistics(self, stats):
        if self.socket:
            self.supervisors.logger.debug('send Statistics {}'.format(stats))
            self.socket.send_string(STATISTICS_HEADER, zmq.SNDMORE)
            self.socket.send_json(status.to_json())
