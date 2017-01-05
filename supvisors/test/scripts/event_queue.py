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

from Queue import Queue

from supvisors.client.subscriber import *


class SupvisorsEventQueues(SupvisorsEventInterface):
    """ The SupvisorsEventQueues is a python thread that connects to Supvisors
    and stores the application and process events received into queues. """

    def __init__(self, port, logger):
        """ Initialization of the attributes.
        Test relies on 3 addresses so theoretically, we only need 3 notifications to know which address is RUNNING or not.
        The asynchronism forces to work on 5 notifications.
        The startsecs of the ini file of this program is then set to 30 seconds.
        """
        SupvisorsEventInterface.__init__(self, create_zmq_context(), port, logger)
        # create a set of addresses
        self.addresses = set()
        # create queues to store messages
        self.event_queues = (Queue(), Queue(), Queue())
        # subscribe to address status only
        self.subscriber.subscribe_address_status()
        self.nb_address_notifications = 0
 
    def on_address_status(self, data):
        """ Pushes the AddressStatus message into a queue. """
        self.logger.info('got AddressStatus message: {}'.format(data))
        if data['statename'] == 'RUNNING':
            self.addresses.add(data['address_name'])
        # check the number of notifications
        self.nb_address_notifications += 1
        if self.nb_address_notifications == 5:
            self.logger.info('addresses: {}'.format(self.addresses))
            # got all notification, unsubscribe from AddressStatus
            self.subscriber.unsubscribe_address_status()
            # subscribe to application and process status
            self.subscriber.subscribe_application_status()
            self.subscriber.subscribe_process_status()
            # notify CheckSequence with an event in start_queue
            self.event_queues[0].put(self.addresses)

    def on_application_status(self, data):
        """ Pushes the ApplicationStatus message into a queue. """
        self.logger.info('got ApplicationStatus message: {}'.format(data))
        self.event_queues[1].put(data)

    def on_process_status(self, data):
        """ Pushes the ProcessStatus message into a queue. """
        self.logger.info('got ProcessStatus message: {}'.format(data))
        self.event_queues[2].put(data)
