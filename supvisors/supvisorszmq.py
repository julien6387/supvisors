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
from zmq.error import ZMQError

from sys import stderr
from typing import Any, Mapping, Optional, Tuple, Union

from supervisor.loggers import Logger

from .ttypes import NameList, Payload
from .utils import *

# Constant for Zmq sockets
INPROC_NAME = 'supvisors'
ZMQ_LINGER = 0

# reference to the Zmq Context instance
ZmqContext = zmq.Context.instance()


class InternalEventPublisher(object):
    """ This class is the wrapper of the PyZmq socket that publishes the events to the Supvisors instances.

    Attributes are:
        - logger: a reference to the Supvisors logger,
        - address: the address name where this process is running,
        - socket: the ZeroMQ socket with a PUBLISH pattern, bound on the internal_port defined
          in the ['supvisors'] section of the Supervisor configuration file.
    """

    def __init__(self, node_name: str, port: int, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param node_name: the name of the local node, used to identify the origin of the messages sent
        :param port: the port number of the TCP socket
        :param logger: the Supvisors logger
        """
        # keep a reference to supvisors' logger
        self.logger = logger
        # keep local node name
        self.node_name = node_name
        # create ZMQ socket
        self.socket = ZmqContext.socket(zmq.PUB)
        url = 'tcp://*:{}'.format(port)
        self.logger.info('binding InternalEventPublisher to %s' % url)
        self.socket.bind(url)

    def close(self) -> None:
        """ This method closes the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def send_tick_event(self, payload: Payload) -> None:
        """ Publish the tick event with PyZmq.

        :param payload: the payload to publish
        :return: None
        """
        self.logger.trace('send TickEvent {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.TICK.value, self.node_name, payload))

    def send_process_event(self, payload: Payload) -> None:
        """ Publish the process event with PyZmq.

        :param payload: the payload to publish
        :return: None
        """
        self.logger.trace('send ProcessEvent {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.PROCESS.value, self.node_name, payload))

    def send_statistics(self, payload: Payload) -> None:
        """ Publish the statistics with PyZmq.

        :param payload: the payload to publish
        :return: None
        """
        self.logger.trace('send Statistics {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.STATISTICS.value, self.node_name, payload))

    def send_state_event(self, payload: Payload) -> None:
        """ Publish the Master state event with PyZmq.

        :param payload: the payload to publish
        :return: None
        """
        self.logger.trace('send Supvisors state {}'.format(payload))
        self.socket.send_pyobj((InternalEventHeaders.STATE.value, self.node_name, payload))


class InternalEventSubscriber(object):
    """ Class for subscription to Listener events.

    Attributes:
        - port: the port number used for internal events,
        - socket: the PyZMQ subscriber.
    """

    def __init__(self, node_names: NameList, port: int):
        """ Initialization of the attributes.

        :param node_names: the names of the publishing nodes
        :param port: the port number of the TCP socket
        """
        self.port = port
        self.socket = ZmqContext.socket(zmq.SUB)
        # connect all addresses
        for node_name in node_names:
            url = 'tcp://{}:{}'.format(node_name, self.port)
            self.socket.connect(url)
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

    def close(self) -> None:
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def receive(self) -> Any:
        """ Reception and de-serialization of a pyobj message.

        :return: the message de-serialized
        """
        return self.socket.recv_pyobj(zmq.NOBLOCK)

    def disconnect(self, node_names: NameList) -> None:
        """ This method disconnects from the PyZmq socket all nodes passed in parameter.

        :param node_names: the names of the nodes to disconnect from the subscriber socket
        :return: None
        """
        for node_name in node_names:
            url = 'tcp://{}:{}'.format(node_name, self.port)
            self.socket.disconnect(url)


class EventPublisher(object):
    """ Class for PyZmq publication of Supvisors events. """

    def __init__(self, port: int, logger: Logger):
        """ Initialization of the attributes.

        :param port: the port number of the TCP socket
        :param logger: the Supvisors logger
        """
        self.logger = logger
        self.socket = ZmqContext.socket(zmq.PUB)
        # WARN: this is a local binding, only visible to processes located on the same address
        url = 'tcp://127.0.0.1:%d' % port
        self.logger.info('binding local Supvisors EventPublisher to %s' % url)
        self.socket.bind(url)

    def close(self) -> None:
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def send_supvisors_status(self, status: Payload) -> None:
        """ Send a JSON-serialized supvisors status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace('send SupvisorsStatus {}'.format(status))
        self.socket.send_string(EventHeaders.SUPVISORS, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_address_status(self, status: Payload) -> None:
        """ Send a JSON-serialized address status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace('send AddressStatus {}'.format(status))
        self.socket.send_string(EventHeaders.ADDRESS, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_application_status(self, status: Payload) -> None:
        """ Send a JSON-serialized application status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace('send ApplicationStatus {}'.format(status))
        self.socket.send_string(EventHeaders.APPLICATION, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_process_event(self, node_name: str, event: Payload) -> None:
        """ Send a JSON-serialized process event through the socket.

        :param node_name: the node name used to identify the origin of the event
        :param event: the event to publish
        :return: None
        """
        # build the event before it is sent
        evt = event.copy()
        evt['address'] = node_name
        self.logger.trace('send Process Event {}'.format(evt))
        self.socket.send_string(EventHeaders.PROCESS_EVENT, zmq.SNDMORE)
        self.socket.send_json(evt)

    def send_process_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the process status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace('send Process Status {}'.format(status))
        self.socket.send_string(EventHeaders.PROCESS_STATUS, zmq.SNDMORE)
        self.socket.send_json(status)


class EventSubscriber(object):
    """ The EventSubscriber wraps the PyZmq socket that connects to **Supvisors**.

    The TCP socket is configured with a PyZmq ``SUBSCRIBE`` pattern.
    It is connected to the **Supvisors** instance running on the localhost and bound on the event port.

    The EventSubscriber requires:
        - the event port number used by **Supvisors** to publish its events,
        - a logger reference to log traces.

    Attributes:
        - logger: the reference to the logger,
        - socket: the PyZmq socket connected to **Supvisors**.
    """

    def __init__(self, zmq_context: zmq.Context, port: int, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param zmq_context: the PyZmq context instance
        :param port: the port number of the TCP socket
        :param logger: the Supvisors logger
        """
        self.logger = logger
        # create ZeroMQ socket
        self.socket = zmq_context.socket(zmq.SUB)
        # WARN: this is a local binding, only visible to processes located on the same address
        url = 'tcp://127.0.0.1:%d' % port
        self.logger.info('connecting EventSubscriber to Supvisors at %s' % url)
        self.socket.connect(url)
        self.logger.debug('EventSubscriber connected')

    def close(self) -> None:
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    # subscription part
    def subscribe_all(self) -> None:
        """ Subscribe to all events.

        :return: None
        """
        self.socket.setsockopt(zmq.SUBSCRIBE, b'')

    def subscribe_supvisors_status(self) -> None:
        """ Subscribe to Supvisors Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.SUPVISORS)

    def subscribe_address_status(self) -> None:
        """ Subscribe to Address Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.ADDRESS)

    def subscribe_application_status(self) -> None:
        """ Subscribe to Application Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.APPLICATION)

    def subscribe_process_event(self) -> None:
        """ Subscribe to Process Event messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_EVENT)

    def subscribe_process_status(self) -> None:
        """ Subscribe to Process Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.PROCESS_STATUS)

    def subscribe(self, code: str) -> None:
        """ Subscribe to the event named code.

        :param code: the message code for subscription
        :return: None
        """
        self.socket.setsockopt(zmq.SUBSCRIBE, code.encode('utf-8'))

    # unsubscription part
    def unsubscribe_all(self) -> None:
        """ Unsubscribe from all events.

        :return: None
        """
        self.socket.setsockopt(zmq.UNSUBSCRIBE, b'')

    def unsubscribe_supvisors_status(self) -> None:
        """ Unsubscribe from Supvisors Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.SUPVISORS)

    def unsubscribe_address_status(self) -> None:
        """ Unsubscribe from Address Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.ADDRESS)

    def unsubscribe_application_status(self) -> None:
        """ Unsubscribe from Application Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.APPLICATION)

    def unsubscribe_process_event(self) -> None:
        """ Unsubscribe from Process Event messages

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_EVENT)

    def unsubscribe_process_status(self) -> None:
        """ Unsubscribe from Process Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.PROCESS_STATUS)

    def unsubscribe(self, code: str) -> None:
        """ Remove subscription to the event named code.

        :param code: the message code for unsubscription
        :return: None
        """
        self.socket.setsockopt(zmq.UNSUBSCRIBE, code.encode('utf-8'))

    # reception part
    def receive(self) -> Tuple[str, Any]:
        """ Reception of two-parts message:
            - header as an unicode string,
            - data encoded in JSON.

        :return: a tuple with header and body
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

    def __init__(self) -> None:
        """ Initialization of the attributes.
        """
        self.socket = ZmqContext.socket(zmq.PULL)
        url = 'inproc://' + INPROC_NAME
        self.socket.connect(url)

    def close(self) -> None:
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def receive(self) -> Any:
        """ Reception and deserialization of the pyobj message.

        :return: the message deserialized
        """
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

    def __init__(self, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param logger: the Supvisors logger
        """
        self.logger = logger
        self.socket = ZmqContext.socket(zmq.PUSH)
        url = 'inproc://' + INPROC_NAME
        self.logger.info('binding RequestPuller to %s' % url)
        self.socket.bind(url)

    def close(self):
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def send_message(self, header: DeferredRequestHeaders, body: Tuple) -> None:
        """ Send request to check authorization to deal with the node.

        :param header: the message type
        :param body: the parameters to send
        :return: None
        """
        self.logger.trace('RequestPusher.send_message: header={}'.format(header.name))
        try:
            self.socket.send_pyobj((header.value, body), zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error('RequestPusher.send_message: {} not sent'.format(header.name))

    def send_check_node(self, node_name: str) -> None:
        """ Send request to check authorization to deal with the node.

        :param node_name: the node name to check
        :return: None
        """
        self.send_message(DeferredRequestHeaders.CHECK_NODE, (node_name,))

    def send_isolate_nodes(self, node_names: NameList) -> None:
        """ Send request to isolate nodes.

        :param node_names: the nodes to isolate
        :return: Node
        """
        self.send_message(DeferredRequestHeaders.ISOLATE_NODES, tuple(node_names))

    def send_start_process(self, node_name: str, namespec: str, extra_args: str) -> None:
        """ Send request to start process.

        :param node_name: the node name where the process has to be started
        :param namespec: the process namespec
        :param extra_args: the additional arguments to be passed to the command line
        :return: None
        """
        self.send_message(DeferredRequestHeaders.START_PROCESS, (node_name, namespec, extra_args))

    def send_stop_process(self, node_name: str, namespec: str) -> None:
        """ Send request to stop process.

        :param node_name: the node name where the process has to be stopped
        :param namespec: the process namespec
        :return: None
        """
        self.send_message(DeferredRequestHeaders.STOP_PROCESS, (node_name, namespec))

    def send_restart(self, node_name: str):
        """ Send request to restart a Supervisor.

        :param node_name: the node name where Supvisors has to be restarted
        :return: None
        """
        self.send_message(DeferredRequestHeaders.RESTART, (node_name,))

    def send_shutdown(self, node_name: str):
        """ Send request to shutdown a Supervisor.

        :param node_name: the node name where Supvisors has to be shut down
        :return: None
        """
        self.send_message(DeferredRequestHeaders.SHUTDOWN, (node_name,))

    def send_restart_all(self, node_name: str):
        """ Send request to restart the Supvisors Master.

        :param node_name: the Supvisors Master
        :return: None
        """
        self.send_message(DeferredRequestHeaders.RESTART_ALL, (node_name,))

    def send_shutdown_all(self, node_name: str):
        """ Send request to shutdown the Supvisors Master.

        :param node_name: the Supvisors Master
        :return: None
        """
        self.send_message(DeferredRequestHeaders.SHUTDOWN_ALL, (node_name,))


class SupervisorZmq(object):
    """ Class for PyZmq context and sockets used from the Supervisor thread.
    This instance owns the PyZmq context that is shared between the Supervisor thread and the Supvisors thread.
    """

    def __init__(self, supvisors: any) -> None:
        """ Create the sockets.

        :param supvisors: the Supvisors global structure
        """
        self.publisher = EventPublisher(supvisors.options.event_port, supvisors.logger)
        self.internal_publisher = InternalEventPublisher(supvisors.address_mapper.local_node_name,
                                                         supvisors.options.internal_port,
                                                         supvisors.logger)
        self.pusher = RequestPusher(supvisors.logger)

    def close(self) -> None:
        """ Close the sockets.

        :return: None
        """
        self.pusher.close()
        self.internal_publisher.close()
        self.publisher.close()


class SupvisorsZmq(object):
    """ Class for PyZmq context and sockets used from the Supvisors thread.
    """

    # timeout for polling in milliseconds
    POLL_TIMEOUT = 500

    # types for annotations
    PollResult = Mapping[Any, int]
    SupvisorsSockets = Union[InternalEventSubscriber, RequestPuller]

    def __init__(self, supvisors) -> None:
        """ Create the sockets and the poller.
        The Supervisor logger cannot be used here (not thread-safe).

        :param supvisors: the Supvisors global structure
        """
        # create zmq sockets
        self.internal_subscriber = InternalEventSubscriber(supvisors.address_mapper.node_names,
                                                           supvisors.options.internal_port)
        self.puller = RequestPuller()
        # create poller
        self.poller = zmq.Poller()
        # register sockets to poller
        self.poller.register(self.internal_subscriber.socket, zmq.POLLIN)
        self.poller.register(self.puller.socket, zmq.POLLIN)

    def poll(self) -> PollResult:
        """ Poll the sockets during POLL_TIMEOUT milliseconds.

        :return: a dictionary of sockets where something happened
        """
        return dict(self.poller.poll(SupvisorsZmq.POLL_TIMEOUT))

    def check_puller(self, poll_result: PollResult) -> Optional[Any]:
        """ Check if something happened on the RequestPuller socket and return message if any.

        :param poll_result: the result of the polling
        :return: the message received if any
        """
        return SupvisorsZmq.check_socket(self.puller, poll_result)

    def check_subscriber(self, poll_result: PollResult) -> Optional[Any]:
        """ Check if something happened on the InternalEventSubscriber socket and return message if any.

        :param poll_result: the result of the polling
        :return: the message received if any
        """
        return SupvisorsZmq.check_socket(self.internal_subscriber, poll_result)

    @staticmethod
    def check_socket(sup_socket: SupvisorsSockets, poll_result: PollResult) -> Optional[Any]:
        """ Check if something happened on the socket and return message if any.

        :param sup_socket: the socket to check
        :param poll_result: the result of the polling
        :return: the message received if any
        """
        if sup_socket.socket in poll_result and poll_result[sup_socket.socket] == zmq.POLLIN:
            try:
                return sup_socket.receive()
            except ZMQError:
                print('[ERROR] failed to get data from socket', file=stderr)

    def disconnect_subscriber(self, node_names: NameList) -> None:
        """ Disconnect the node from subscription socket.

        :param node_names: the name of the node to disconnect
        :return: None
        """
        self.internal_subscriber.disconnect(node_names)

    def close(self) -> None:
        """ Close the poller and the sockets.

        :return: None
        """
        # unregister sockets from poller
        self.poller.unregister(self.puller.socket)
        self.poller.unregister(self.internal_subscriber.socket)
        # close sockets
        self.puller.close()
        self.internal_subscriber.close()
