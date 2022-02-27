#!/usr/bin/python
# -*- coding: utf-8 -*-

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

from time import time
from queue import Empty, Queue

from supvisors.client.subscriber import SupvisorsEventInterface


class SupvisorsEventQueues(SupvisorsEventInterface):
    """ The SupvisorsEventQueues is a client subscriber thread that connects
    to Supvisors and stores the application and process events received
    into queues. """

    PORT = 60002

    def __init__(self, zcontext, logger):
        """ Initialization of the attributes. """
        # create logger using a BoundIO
        SupvisorsEventInterface.__init__(self, zcontext, self.PORT, logger)
        self.subscriber.subscribe_all()
        # create queues to store messages
        self.supvisors_queue = Queue()
        self.instance_queue = Queue()
        self.application_queue = Queue()
        self.process_queue = Queue()
        self.event_queue = Queue()

    # callbacks
    def on_supvisors_status(self, data):
        """ Just logs the contents of the Supvisors Status message. """
        self.logger.info(f'got Supvisors Status message: {data}')
        self.supvisors_queue.put(data)

    def on_instance_status(self, data):
        """ Pushes the Supvisors Instance Status message into a queue. """
        self.logger.info(f'got Supvisors Instance Status message: {data}')
        self.instance_queue.put(data)

    def on_application_status(self, data):
        """ Pushes the Application Status message into a queue. """
        self.logger.info(f'got Application Status message: {data}')
        self.application_queue.put(data)

    def on_process_status(self, data):
        """ Pushes the Process Status message into a queue. """
        self.logger.info(f'got Process Status message: {data}')
        self.process_queue.put(data)

    def on_process_event(self, data):
        """ Pushes the Process Event message into a queue. """
        self.logger.info(f'got Process Event message: {data}')
        self.event_queue.put(data)

    # utilities
    def flush(self):
        """ Empties all queues. """
        self.flush_queue(self.supvisors_queue)
        self.flush_queue(self.instance_queue)
        self.flush_queue(self.application_queue)
        self.flush_queue(self.process_queue)
        self.flush_queue(self.event_queue)

    def flush_queue(self, queue):
        """ Empties all queues. """
        try:
            while True:
                queue.get_nowait()
        except Empty:
            self.logger.debug('queue flushed')

    @staticmethod
    def wait_until_event(queue, sub_event, timeout):
        """ Wait for a specific event on queue for max timeout in seconds. """
        end_date = time() + timeout
        while time() < end_date:
            try:
                event = queue.get(True, 0.5)
            except Empty:
                continue
            # return event if all items of sub_event are in event
            if all(item in event.items() for item in sub_event.items()):
                return event

    @staticmethod
    def wait_until_events(queue, sub_events, timeout):
        """ Wait for a list of specific events on queue for max timeout in seconds. """
        events_received = []
        end_date = time() + timeout
        while time() < end_date:
            try:
                event = queue.get(True, 0.5)
            except Empty:
                continue
            # add event to list if all items of a sub_event are in event
            sub_events_copy = sub_events[:]
            for sub_event in sub_events_copy:
                if sub_event.items() < event.items():
                    events_received.append(event)
                    sub_events.remove(sub_event)
                    # event found. next
                    break
            # done if all received
            if not sub_events:
                end_date = 0
        return events_received
