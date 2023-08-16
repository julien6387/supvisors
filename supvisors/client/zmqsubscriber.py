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

import zmq.asyncio
from supervisor.loggers import Logger

from supvisors.external_com.eventinterface import EventSubscriberInterface
from supvisors.external_com.supvisorszmq import ZmqEventSubscriber
from supvisors.ttypes import Payload


class SupvisorsZmqEventInterface(ZmqEventSubscriber, EventSubscriberInterface):
    """ The SupvisorsZmqEventInterface connects to Supvisors and receives the events published
    using the PyZMQ interface.

    The SupvisorsEventInterface requires:
        - an asynchronous PyZMQ context,
        - the node name where the Supvisors instance is running and publishing its events,
        - the event port number used by the Supvisors instance to publish its events,
        - a logger.

    This event port number MUST correspond to the event_port value set in the [supvisors] section
    of the Supervisor configuration file.

    The default behaviour is to print the messages received.
    For any other behaviour, just specialize the methods on_xxx_status.

    WARN: Notifications are received in the context of the client thread.

    Example:
        import zmq.asyncio
        from supvisors.client.zmqsubscriber import SupvisorsZmqEventInterface

        intf = SupvisorsZmqEventInterface(zmq.asyncio.Context.instance(), 'localhost', 9003, logger)
        intf.subscribe_all()
        intf.start()
        # ... receive notifications ...
        intf.stop()
    """

    def __init__(self, zmq_context: zmq.asyncio.Context, node_name: str, event_port: int, logger: Logger):
        """ Initialization of the attributes. """
        ZmqEventSubscriber.__init__(self, zmq_context, self, node_name, event_port, logger)

    def on_supvisors_status(self, data: Payload) -> None:
        """ Receive and log the contents of the Supvisors Status message.

        :param data: the latest Supvisors status
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_supvisors_status: got Supvisors Status message: {data}')

    def on_instance_status(self, data: Payload) -> None:
        """ Receive and log the contents of the Supvisors Instance Status message.

        :param data: the latest status about a given Supvisors instance
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_instance_status: got Instance Status message: {data}')

    def on_application_status(self, data: Payload) -> None:
        """ Receive and log the contents of the Application Status message.

        :param data: the latest status about a given Application
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_application_status: got Application Status message: {data}')

    def on_process_event(self, data: Payload) -> None:
        """ Receive and log the contents of the Process Event message.

        :param data: the latest event about a given Process
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_process_event: got Process Event message: {data}')

    def on_process_status(self, data: Payload) -> None:
        """ Receive and log the contents of the Process Status message.

        :param data: the latest status about a given Process
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_process_status: got Process Status message: {data}')

    def on_host_statistics(self, data: Payload) -> None:
        """ Receive and log the contents of the Host Statistics message.

        :param data: the latest statistics about a given host where Supvisors is running
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_host_statistics: got Host Statistics message: {data}')

    def on_process_statistics(self, data: Payload) -> None:
        """ Receive and log the contents of the Process Statistics message.

        :param data: the latest statistics about a given process running in Supvisors
        :return: None
        """
        self.logger.info(f'SupvisorsZmqEventInterface.on_process_statistics: got Process Statistics message: {data}')


if __name__ == '__main__':
    """ Test program. """
    import argparse
    import time
    from supervisor.loggers import LevelsByName
    from supvisors.client.clientutils import create_logger

    # get arguments
    parser = argparse.ArgumentParser(description='Start a subscriber to Supvisors events.')
    parser.add_argument('-n', '--node', type=str, default='127.0.0.1', help='the Supvisors node name')
    parser.add_argument('-p', '--port', type=int, default=60002, help='the Supvisors event port')
    parser.add_argument('-s', '--sleep', type=int, metavar='SEC', default=20,
                        help='the duration of the subscription')
    args = parser.parse_args()
    # create test subscriber
    zmq_intf = SupvisorsZmqEventInterface(zmq.asyncio.Context.instance(), args.node, args.port,
                                          create_logger(loglevel=LevelsByName.INFO))
    zmq_intf.subscribe_all()
    # start thread and sleep for a while
    zmq_intf.start()
    time.sleep(args.sleep)
    # stop thread and halt
    zmq_intf.stop()
