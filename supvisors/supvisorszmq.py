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

import zmq

from supervisor.loggers import Logger

from supvisors.ttypes import Payload
from supvisors.utils import *

# Constant for Zmq sockets
INPROC_NAME = 'supvisors'
ZMQ_LINGER = 0

# reference to the Zmq Context instance
ZmqContext = zmq.Context.instance()


class InternalEventPublisher(object):
    """ This class is the wrapper of the ZeroMQ socket that publishes the events
    to the Supvisors instances.

    Attributes are:

        - logger: a reference to the Supvisors logger,
        - address: the address name where this process is running,
        - socket: the ZeroMQ socket with a PUBLISH pattern, bound on the internal_port defined in the ['supvisors'] section of the Supervisor configuration file.
    """

    def __init__(self, address: str, port: int, logger: Logger) -> None:
        """ Initialization of the attributes. """
        # keep a reference to supvisors
        self.logger = logger
        # get local address
        self.address = address
        # create ZMQ socket
        self.socket = ZmqContext.socket(zmq.PUB)
        url = 'tcp://*:{}'.format(port)
        self.logger.info('binding InternalEventPublisher to %s' % url)
        self.socket.bind(url)

    def close(self) -> None:
        """ This method closes the PyZMQ socket. """
        self.socket.close(ZMQ_LINGER)

    def send_tick_event(self, payload: Payload) -> None:
        """ Publishes the tick event with ZeroMQ. """
        self.logger.trace('send TickEvent {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.TICK, self.address, payload))

    def send_process_event(self, payload: Payload) -> None:
        """ Publishes the process event with ZeroMQ. """
        self.logger.trace('send ProcessEvent {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.PROCESS, self.address, payload))

    def send_statistics(self, payload: Payload) -> None:
        """ Publishes the statistics with ZeroMQ. """
        self.logger.trace('send Statistics {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.STATISTICS, self.address, payload))


class InternalEventSubscriber(object):
    """ Class for subscription to Listener events.

    Attributes:
        - port: the port number used for internal events,
        - socket: the PyZMQ subscriber.
    """

    def __init__(self, addresses, port: int):
        """ Initialization of the attributes. """
        self.port = port
        self.socket = ZmqContext.socket(zmq.SUB)
        # connect all addresses
        for address in addresses:
            url = 'tcp://{}:{}'.format(address, self.port)
            self.socket.connect(url)
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

    def close(self) -> None:
        """ This method closes the PyZMQ socket. """
        self.socket.close(ZMQ_LINGER)

    def receive(self):
        """ Reception and pyobj de-serialization of one message. """
        return self.socket.recv_pyobj(zmq.NOBLOCK)

    def disconnect(self, addresses) -> None:
        """ This method disconnects from the PyZMQ socket all addresses passed in parameter. """
        for address in addresses:
            url = 'tcp://{}:{}'.format(address, self.port)
            self.socket.disconnect(url)


class EventPublisher(object):
    """ Class for ZMQ publication of Supvisors events. """

    def __init__(self, port, logger):
        """ Initialization of the attributes. """
        self.logger = logger
        self.socket = ZmqContext.socket(zmq.PUB)
        # WARN: this is a local binding, only visible to processes located on the same address
        url = 'tcp://127.0.0.1:%d' % port
        self.logger.info('binding local Supvisors EventPublisher to %s' % url)
        self.socket.bind(url)

    def close(self) -> None:
        """ This method closes the PyZMQ socket. """
        self.socket.close(ZMQ_LINGER)

    def send_supvisors_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the supvisors status through the socket. """
        self.logger.trace('send SupvisorsStatus {}'.format(status))
        self.socket.send_string(EventHeaders.SUPVISORS, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_address_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the address status through the socket. """
        self.logger.trace('send AddressStatus {}'.format(status))
        self.socket.send_string(EventHeaders.ADDRESS, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_application_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the application status through the socket. """
        self.logger.trace('send ApplicationStatus {}'.format(status))
        self.socket.send_string(EventHeaders.APPLICATION, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_process_event(self, address: str, event: Payload) -> None:
        """ This method sends a process event through the socket. """
        # build the event before it is sent
        evt = event.copy()
        evt['address'] = address
        self.logger.trace('send Process Event {}'.format(evt))
        self.socket.send_string(EventHeaders.PROCESS_EVENT, zmq.SNDMORE)
        self.socket.send_json(evt)

    def send_process_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the process status through the socket. """
        self.logger.trace('send Process Status {}'.format(status))
        self.socket.send_string(EventHeaders.PROCESS_STATUS, zmq.SNDMORE)
        self.socket.send_json(status)


class EventSubscriber(object):
    """ The EventSubscriber wraps the ZeroMQ socket that connects
    to **Supvisors**.

    The TCP socket is configured with a ZeroMQ ``SUBSCRIBE`` pattern.
    It is connected to the **Supvisors** instance running on the localhost
    and bound on the event port.

    The EventSubscriber requires:

        - the event port number used by **Supvisors** to publish its events,
        - a logger reference to log traces.

    Attributes:

        - logger: the reference to the logger,
        - socket: the ZeroMQ socket connected to **Supvisors**.
    """

    def __init__(self, zmq_context, port, logger):
        """ Initialization of the attributes. """
        self.logger = logger
        # create ZeroMQ socket
        self.socket = zmq_context.socket(zmq.SUB)
        # WARN: this is a local binding, only visible to processes
        # located on the same address
        url = 'tcp://127.0.0.1:%d' % port
        self.logger.info('connecting EventSubscriber to Supvisors at %s' % url)
        self.socket.connect(url)
        self.logger.debug('EventSubscriber connected')

    def close(self):
        """ Close the ZeroMQ socket. """
        self.socket.close(ZMQ_LINGER)

    # subscription part
    def subscribe_all(self):
        """ Subscription to all events. """
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

    def subscribe_supvisors_status(self):
        """ Subscription to Supvisors Status messages. """
        self.subscribe(EventHeaders.SUPVISORS)

    def subscribe_address_status(self):
        """ Subscription to Address Status messages. """
        self.subscribe(EventHeaders.ADDRESS)

    def subscribe_application_status(self):
        """ Subscription to Application Status messages. """
        self.subscribe(EventHeaders.APPLICATION)

    def subscribe_process_event(self):
        """ Subscription to Process Event messages. """
        self.subscribe(EventHeaders.PROCESS_EVENT)

    def subscribe_process_status(self):
        """ Subscription to Process Status messages. """
        self.subscribe(EventHeaders.PROCESS_STATUS)

    def subscribe(self, code):
        """ Subscription to the event named code. """
        self.socket.setsockopt(zmq.SUBSCRIBE, code.encode('utf-8'))

    # unsubscription part
    def unsubscribe_all(self):
        """ Subscription to all events. """
        self.socket.setsockopt(zmq.UNSUBSCRIBE, b'')

    def unsubscribe_supvisors_status(self):
        """ Subscription to Supvisors Status messages. """
        self.unsubscribe(EventHeaders.SUPVISORS)

    def unsubscribe_address_status(self):
        """ Subscription to Address Status messages. """
        self.unsubscribe(EventHeaders.ADDRESS)

    def unsubscribe_application_status(self):
        """ Subscription to Application Status messages. """
        self.unsubscribe(EventHeaders.APPLICATION)

    def unsubscribe_process_event(self):
        """ Subscription to Process Event messages. """
        self.unsubscribe(EventHeaders.PROCESS_EVENT)

    def unsubscribe_process_status(self):
        """ Subscription to Process Status messages. """
        self.unsubscribe(EventHeaders.PROCESS_STATUS)

    def unsubscribe(self, code):
        """ Remove subscription to the event named code. """
        self.socket.setsockopt(zmq.UNSUBSCRIBE, code.encode('utf-8'))

    # reception part
    def receive(self):
        """ Reception of two-parts message:

            - header as an unicode string,
            - data encoded in JSON.
        """
        return self.socket.recv_string(), self.socket.recv_json()


class RequestPuller(object):
    """ Class for pulling deferred XML-RPC.

    Attributes:
        - socket: the PyZMQ puller.

    As it uses an inproc transport, this implies the following conditions:
        - the RequestPusher instance and the RequestPuller instance MUST share the same ZMQ context,
        - the RequestPusher instance MUST be created before the RequestPuller instance.
    """

    def __init__(self):
        """ Initialization of the attributes. """
        self.socket = ZmqContext.socket(zmq.PULL)
        url = 'inproc://' + INPROC_NAME
        self.socket.connect(url)

    def close(self):
        """ This method closes the PyZMQ socket. """
        self.socket.close(ZMQ_LINGER)

    def receive(self):
        """ Reception and pyobj deserialization of one message. """
        return self.socket.recv_pyobj()


class RequestPusher(object):
    """ Class for pushing deferred XML-RPC.

    Attributes:
        - logger: a reference to the Supvisors logger,
        - socket: the PyZMQ pusher.

    As it uses an inproc transport, this implies the following conditions:
        - the RequestPusher instance and the RequestPuller instance MUST share the same ZMQ context,
        - the RequestPusher instance MUST be created before the RequestPuller instance.
    """

    def __init__(self, logger):
        """ Initialization of the attributes. """
        self.logger = logger
        self.socket = ZmqContext.socket(zmq.PUSH)
        url = 'inproc://' + INPROC_NAME
        self.logger.info('binding RequestPuller to %s' % url)
        self.socket.bind(url)

    def close(self):
        """ This method closes the PyZMQ socket. """
        self.socket.close(ZMQ_LINGER)

    def send_check_address(self, address_name: str) -> None:
        """ Send request to check address. """
        self.logger.debug('RequestPusher.send_check_address: address_name={}'.format(address_name))
        try:
            self.socket.send_pyobj((DeferredRequestHeaders.CHECK_ADDRESS, (address_name,)),
                                   zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('RequestPusher.send_check_address: CHECK_ADDRESS not sent')

    def send_isolate_addresses(self, address_names):
        """ Send request to isolate address. """
        self.logger.trace('RequestPusher.send_isolate_addresses: address_names={}'.format(address_names))
        try:
            self.socket.send_pyobj((DeferredRequestHeaders.ISOLATE_ADDRESSES, address_names),
                                   zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('RequestPusher.send_isolate_addresses: ISOLATE_ADDRESSES not sent')

    def send_start_process(self, address_name, namespec, extra_args):
        """ Send request to start process. """
        self.logger.trace('send START_PROCESS {} to {} with {}'.format(namespec, address_name, extra_args))
        try:
            self.socket.send_pyobj((DeferredRequestHeaders.START_PROCESS, (address_name, namespec, extra_args)),
                                   zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('START_PROCESS not sent')

    def send_stop_process(self, address_name, namespec):
        """ Send request to stop process. """
        self.logger.trace('send STOP_PROCESS {} to {}'.format(namespec, address_name))
        try:
            self.socket.send_pyobj((DeferredRequestHeaders.STOP_PROCESS, (address_name, namespec)),
                                   zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('STOP_PROCESS not sent')

    def send_restart(self, address_name):
        """ Send request to restart a Supervisor. """
        self.logger.trace('send RESTART {}'.format(address_name))
        try:
            self.socket.send_pyobj((DeferredRequestHeaders.RESTART, (address_name,)),
                                   zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('RESTART not sent')

    def send_shutdown(self, address_name):
        """ Send request to shutdown a Supervisor. """
        self.logger.trace('send SHUTDOWN {}'.format(address_name))
        try:
            self.socket.send_pyobj((DeferredRequestHeaders.SHUTDOWN, (address_name,)),
                                   zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('SHUTDOWN not sent')


class SupervisorZmq(object):
    """ Class for PyZmq context and sockets used from the Supervisor thread.
    This instance owns the PyZmq context that is shared between the Supervisor thread and the Supvisors thread.
    """

    def __init__(self, supvisors):
        """ Create the sockets. """
        self.publisher = EventPublisher(supvisors.options.event_port, supvisors.logger)
        self.internal_publisher = InternalEventPublisher(supvisors.address_mapper.local_address,
                                                         supvisors.options.internal_port,
                                                         supvisors.logger)
        self.pusher = RequestPusher(supvisors.logger)

    def close(self):
        """ Close the sockets. """
        self.pusher.close()
        self.internal_publisher.close()
        self.publisher.close()


class SupvisorsZmq(object):
    """ Class for PyZmq context and sockets used from the Supvisors thread.
    """

    def __init__(self, supvisors):
        """ Create the sockets.
        The Supervisor logger cannot be used here (not thread-safe). """
        self.internal_subscriber = InternalEventSubscriber(supvisors.address_mapper.addresses,
                                                           supvisors.options.internal_port)
        self.puller = RequestPuller()

    def close(self):
        """ Close the sockets. """
        self.puller.close()
        self.internal_subscriber.close()
