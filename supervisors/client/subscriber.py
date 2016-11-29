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
import zmq

from supervisor.loggers import LevelsByName, getLogger

from supervisors.utils import *


def create_zmq_context():
    """ Return a new ZeroMQ context.
    LINGER option is set to force the sockets to close immediately. """
    zmq_context = zmq.Context.instance()
    zmq_context.setsockopt(zmq.LINGER, 0)
    return zmq_context


def create_logger(logfile='subscriber.log', loglevel=LevelsByName.INFO,
        format='%(asctime)s %(levelname)s %(message)s\n',
        rotating=True, maxbytes=10*1024*1024, backups=1, stdout=True):
    """ Return a Supervisor logger. """
    return getLogger(logfile, loglevel, format, rotating, maxbytes, backups, stdout)


class SupervisorsEventSubscriber(object):
    """ The SupervisorsEventSubscriber wraps the ZeroMQ socket that connects to Supervisors.

    The TCP socket is configured with a ZeroMQ SUBSCRIBE pattern.
    It is connected to the Supervisors instance running on the localhost and bound on the event port.

    The SupervisorsEventSubscriber requires:
    - a ZeroMQ context,
    - the event port number used by Supervisors to publish its events,
    - a logger reference to log traces.

    Attributes:
    - logger: the reference to the logger,
    - socket: the ZeroMQ socket connected to Supervisors. """

    def __init__(self, zmq_context, event_port, logger):
        """ Initialization of the attributes. """
        self.logger = logger
        # create ZeroMQ socket
        self.socket = zmq_context.socket(zmq.SUB)
        # WARN: this is a local binding, only visible to processes located on the same address
        url = 'tcp://127.0.0.1:{}'.format(event_port)
        self.logger.info('connecting EventSubscriber to Supervisors at %s' % url)
        self.socket.connect(url)
        self.logger.debug('EventSubscriber connected')

    def subscribe_all(self):
        """ Subscription to all events. """
        self.socket.setsockopt(zmq.SUBSCRIBE, '')

    def subscribe_supervisors_status(self):
        """ Subscription to Supervisors status events. """
        self.subscribe(SUPERVISORS_STATUS_HEADER)

    def subscribe_address_status(self):
        """ Subscription to Address status events. """
        self.subscribe(ADDRESS_STATUS_HEADER)

    def subscribe_application_status(self):
        """ Subscription to Application status events. """
        self.subscribe(APPLICATION_STATUS_HEADER)

    def subscribe_process_status(self):
        """ Subscription to Process status events. """
        self.subscribe(PROCESS_STATUS_HEADER)

    def subscribe(self, code):
        """ Subscription to the event named code. """
        self.socket.setsockopt(zmq.SUBSCRIBE, code.encode('utf-8'))

    def close(self):
        """ Close the ZeroMQ socket. """
        if self.socket:
            self.socket.close()
            self.socket = None

    def receive(self):
        """ Reception of two-parts message:
        - header as an unicode string,
        - data encoded in JSON. """
        return self.socket.recv_string(), self.socket.recv_json()


class SupervisorsEventInterface(threading.Thread):
    """ The SupervisorsEventInterface is a python thread that connects to Supervisors
    and receives the events published.
    The subscriber attribute shall be used to define the event types of interest.

    The SupervisorsEventInterface requires:
    - a ZeroMQ context,
    - the event port number used by Supervisors to publish its events,
    - a logger reference to log traces.

    This event port number MUST correspond to the event_port value set in the [supervisors]
    section of the Supervisor configuration file.

    Attributes:
    - logger: the reference to the logger,
    - subscriber: the wrapper of the ZeroMQ socket connected to Supervisors,
    - loop: when set to False, breaks the infinite loop of the thread.
    
    Constants:
    - _Poll_timeout: duration used to time out the ZeroMQ poller, set to 1000 milli-seconds. """

    _Poll_timeout = 1000

    def __init__(self, zmq_context, event_port, logger):
        """ Initialization of the attributes. """
        # thread attributes
        threading.Thread.__init__(self)
        # keep a reference to the logger
        self.logger = logger
        # create event socket
        self.subscriber = SupervisorsEventSubscriber(zmq_context, event_port, logger)

    def stop(self):
        """ This method stops the main loop of the thread. """
        self.logger.info('request to stop main loop')
        self.loop = False

    def run(self):
        """ Main loop of the thread. """
        # create poller and register event subscriber
        poller = zmq.Poller()
        poller.register(self.subscriber.socket, zmq.POLLIN) 
        # poll events every seconds
        self.loop = True
        self.logger.info('entering main loop')
        while self.loop:
            socks = dict(poller.poll(self._Poll_timeout))
            # check if something happened on the socket
            if self.subscriber.socket in socks and socks[self.subscriber.socket] == zmq.POLLIN:
                self.logger.debug('got message on subscriber')
                try:
                    message = self.subscriber.receive()
                except Exception, e:
                    self.logger.error('failed to get data from subscriber: {}'.format(e.message))
                else:
                    if message[0] == SUPERVISORS_STATUS_HEADER:
                        self.on_supervisors_status(message[1])
                    elif message[0] == ADDRESS_STATUS_HEADER:
                        self.on_address_status(message[1])
                    elif message[0] == APPLICATION_STATUS_HEADER:
                        self.on_application_status(message[1])
                    elif message[0] == PROCESS_STATUS_HEADER:
                        self.on_process_status(message[1])
        self.logger.warn('exiting main loop')
        self.subscriber.close()

    def on_supervisors_status(self, data):
        """ Just logs the contents of the SupervisorsStatus message. """
        self.logger.info('got SupervisorsStatus message: {}'.format(data))

    def on_address_status(self, data):
        """ Just logs the contents of the AddressStatus message. """
        self.logger.info('got AddressStatus message: {}'.format(data))

    def on_application_status(self, data):
        """ Just logs the contents of the ApplicationStatus message. """
        self.logger.info('got ApplicationStatus message: {}'.format(data))

    def on_process_status(self, data):
        """ Just logs the contents of the ProcessStatus message. """
        self.logger.info('got ApplicationStatus message: {}'.format(data))


if __name__ == '__main__':
    # get arguments
    import argparse, time
    parser = argparse.ArgumentParser(description='Start a subscriber to Supervisors events.')
    parser.add_argument('-p', '--port', type=int, default=65002, help="the event port of Supervisors")
    parser.add_argument('-s', '--sleep', type=int, metavar='SEC', default=10,
        help="the duration of the subscription")
    args = parser.parse_args()
    # create test subscriber
    loop = SupervisorsEventInterface(create_zmq_context(), args.port, create_logger())
    loop.subscriber.subscribe_all()
    # start thread and sleep for a while
    loop.start()
    time.sleep(args.sleep)
    # stop thread and halt
    loop.stop()
    loop.join()

