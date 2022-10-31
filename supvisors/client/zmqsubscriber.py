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

import threading
import zmq

from supervisor import loggers
from supervisor.loggers import LevelsByName

from supvisors.supvisorszmq import EventSubscriber
from supvisors.ttypes import EventHeaders


def create_logger(logfile=r'subscriber.log', loglevel=LevelsByName.INFO,
                  fmt='%(asctime)s;%(levelname)s;%(message)s\n',
                  rotating=True, maxbytes=10 * 1024 * 1024, backups=1, stdout=True):
    """ Return a Supervisor logger. """
    logger = loggers.getLogger(loglevel)
    if stdout:
        loggers.handle_stdout(logger, fmt)
    loggers.handle_file(logger, logfile, fmt, rotating, maxbytes, backups)
    return logger


class SupvisorsZmqEventInterface(threading.Thread):
    """ The *SupvisorsEventInterface* is a python thread that connects to |Supvisors| and receives the events published.
    The subscriber attribute shall be used to define the event types of interest.

    The *SupvisorsEventInterface* requires:
        - a PyZMQ_ context,
        - the event port number used by **Supvisors** to publish its events,
        - a logger reference to log traces.

    This event port number MUST correspond to the ``event_port`` value set in the ``[supvisors]`` section
    of the |Supervisor| configuration file.

    The default behaviour is to print the messages received.
    For any other behaviour, just specialize the methods `on_xxx_status`.

    Attributes:
        - logger: the reference to the logger,
        - subscriber: the wrapper of the PyZMQ_ socket connected to |Supvisors|,
        - stop_event: when set, breaks the infinite loop of the thread.

    Constants:
        - _Poll_timeout: duration used to time out the PyZMQ_ poller, defaulted to 500 milliseconds.
    """

    _Poll_timeout = 500

    def __init__(self, zmq_context, event_port, logger):
        """ Initialization of the attributes. """
        # thread attributes
        threading.Thread.__init__(self)
        # store the parameters
        self.zmq_context = zmq_context
        self.event_port = event_port
        self.logger = logger
        # create event socket
        self.subscriber = EventSubscriber(self.zmq_context, self.event_port, self.logger)
        # create stop event
        self.stop_event = threading.Event()

    def stop(self):
        """ This method stops the main loop of the thread. """
        self.logger.info('SupvisorsEventInterface.stop: request to stop main loop')
        self.stop_event.set()

    def run(self):
        """ Main loop of the thread. """
        # create poller and register event subscriber
        poller = zmq.Poller()
        poller.register(self.subscriber.socket, zmq.POLLIN)
        # poll events every seconds
        self.logger.info('SupvisorsEventInterface.run: entering main loop')
        while not self.stop_event.is_set():
            socks = dict(poller.poll(self._Poll_timeout))
            # check if something happened on the socket
            if self.subscriber.socket in socks and socks[self.subscriber.socket] == zmq.POLLIN:
                self.logger.debug('SupvisorsEventInterface.run: got message on subscriber')
                try:
                    message = self.subscriber.receive()
                except zmq.ZMQError as exc:
                    self.logger.error(f'SupvisorsEventInterface.run: failed to get data from subscriber: {exc}')
                else:
                    try:
                        event = EventHeaders(message[0])
                    except ValueError:
                        self.logger.error(f'SupvisorsEventInterface.run: unexpected event type {message[0]}')
                    else:
                        if event == EventHeaders.SUPVISORS:
                            self.on_supvisors_status(message[1])
                        elif event == EventHeaders.INSTANCE:
                            self.on_instance_status(message[1])
                        elif event == EventHeaders.APPLICATION:
                            self.on_application_status(message[1])
                        elif event == EventHeaders.PROCESS_EVENT:
                            self.on_process_event(message[1])
                        elif event == EventHeaders.PROCESS_STATUS:
                            self.on_process_status(message[1])
        self.logger.warn('SupvisorsEventInterface.run: exiting main loop')
        self.subscriber.close()

    def on_supvisors_status(self, data):
        """ Just logs the contents of the |Supvisors| Status message. """
        self.logger.info(f'SupvisorsEventInterface.on_supvisors_status: got Supvisors Status message: {data}')

    def on_instance_status(self, data):
        """ Just logs the contents of the Supvisors Instance Status message. """
        self.logger.info(f'SupvisorsEventInterface.on_instance_status: got Instance Status message: {data}')

    def on_application_status(self, data):
        """ Just logs the contents of the Application Status message. """
        self.logger.info(f'SupvisorsEventInterface.on_application_status: got Application Status message: {data}')

    def on_process_event(self, data):
        """ Just logs the contents of the Process Event message. """
        self.logger.info(f'SupvisorsEventInterface.on_process_event: got Process Event message: {data}')

    def on_process_status(self, data):
        """ Just logs the contents of the Process Status message. """
        self.logger.info(f'SupvisorsEventInterface.on_process_status: got Process Status message: {data}')


if __name__ == '__main__':
    import argparse
    import time
    # get arguments
    parser = argparse.ArgumentParser(description='Start a subscriber to Supvisors events.')
    parser.add_argument('-p', '--port', type=int, default=60002, help='the event port of Supvisors')
    parser.add_argument('-s', '--sleep', type=int, metavar='SEC', default=10,
                        help='the duration of the subscription')
    args = parser.parse_args()
    # create test subscriber
    loop = SupvisorsZmqEventInterface(zmq.Context.instance(), args.port, create_logger())
    loop.subscriber.subscribe_all()
    # start thread and sleep for a while
    loop.start()
    time.sleep(args.sleep)
    # stop thread and halt
    loop.stop()
    loop.join()
