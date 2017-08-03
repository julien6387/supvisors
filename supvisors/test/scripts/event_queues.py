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
from Queue import Queue

from supvisors.client.subscriber import SupvisorsEventInterface, create_logger


class SupvisorsEventQueues(SupvisorsEventInterface):
    """ The SupvisorsEventQueues is a client subscriber thread that connects
    to Supvisors and stores the application and process events received
    into queues. """

    PORT = 60002

    def __init__(self):
        """ Initialization of the attributes. """
        # create logger using a BoundIO
        SupvisorsEventInterface.__init__(self,
                                         zmq.Context.instance(),
                                         self.PORT,
                                         create_logger(logfile=None))
        # create queues to store messages
        self.supvisors_queue = Queue()
        self.address_queue = Queue()
        self.application_queue = Queue()
        self.process_queue = Queue()
        self.event_queue = Queue()

    def on_supvisors_status(self, data):
        """ Just logs the contents of the Supvisors Status message. """
        self.logger.info('got Supvisors Status message: {}'.format(data))
        self.supvisors_queue.put(data)

    def on_address_status(self, data):
        """ Pushes the Address Status message into a queue. """
        self.logger.info('got Address Status message: {}'.format(data))
        self.address_queue.put(data)

    def on_application_status(self, data):
        """ Pushes the Application Status message into a queue. """
        self.logger.info('got Application Status message: {}'.format(data))
        self.application_queue.put(data)

    def on_process_status(self, data):
        """ Pushes the Process Status message into a queue. """
        self.logger.info('got Process Status message: {}'.format(data))
        self.process_queue.put(data)

    def on_process_event(self, data):
        """ Pushes the Process Event message into a queue. """
        self.logger.info('got Process Event message: {}'.format(data))
        self.event_queue.put(data)
