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
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from supervisor.loggers import Logger

from .supvisorsmapper import SupvisorsInstanceId, SupvisorsMapper
from .ttypes import NameList, Payload
from .utils import *

# Constant for Zmq sockets
INPROC_NAME = 'supvisors'
ZMQ_LINGER = 0

# reference to the Zmq Context instance
ZmqContext = zmq.Context.instance()


class EventPublisher(object):
    """ Class for PyZmq publication of Supvisors events. """

    def __init__(self, instance: SupvisorsInstanceId, logger: Logger):
        """ Initialization of the attributes.

        :param port: the port number of the TCP socket
        :param logger: the Supvisors logger
        """
        self.logger = logger
        self.socket = ZmqContext.socket(zmq.PUB)
        # WARN: this is a local binding, only visible to processes located on the same host
        url = f'tcp://127.0.0.1:{instance.event_port}'
        self.logger.debug(f'EventPublisher: binding {url}')
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
        self.logger.trace(f'EventPublisher.send_supvisors_status: {status}')
        self.socket.send_string(EventHeaders.SUPVISORS, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_instance_status(self, status: Payload) -> None:
        """ Send a JSON-serialized Supvisors instance status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'EventPublisher.send_instance_status: {status}')
        self.socket.send_string(EventHeaders.INSTANCE, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_application_status(self, status: Payload) -> None:
        """ Send a JSON-serialized application status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'EventPublisher.send_application_status: {status}')
        self.socket.send_string(EventHeaders.APPLICATION, zmq.SNDMORE)
        self.socket.send_json(status)

    def send_process_event(self, identifier: str, event: Payload) -> None:
        """ Send a JSON-serialized process event through the socket.

        :param identifier: the identifier used to identify the origin of the event
        :param event: the event to publish
        :return: None
        """
        # build the event before it is sent
        evt = event.copy()
        evt['identifier'] = identifier
        self.logger.trace(f'EventPublisher.send_process_event: {evt}')
        self.socket.send_string(EventHeaders.PROCESS_EVENT, zmq.SNDMORE)
        self.socket.send_json(evt)

    def send_process_status(self, status: Payload) -> None:
        """ This method sends a serialized form of the process status through the socket.

        :param status: the status to publish
        :return: None
        """
        self.logger.trace(f'EventPublisher.send_process_status: {status}')
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
        # WARN: this is a local binding, only visible to processes located on the same host
        url = f'tcp://127.0.0.1:{port}'
        self.logger.debug(f'EventSubscriber: connecting {url}')
        self.socket.connect(url)

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

    def subscribe_instance_status(self) -> None:
        """ Subscribe to Supvisors Instance Status messages.

        :return: None
        """
        self.subscribe(EventHeaders.INSTANCE)

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

    def unsubscribe_instance_status(self) -> None:
        """ Unsubscribe from Supvisors Instance Status messages

        :return: None
        """
        self.unsubscribe(EventHeaders.INSTANCE)

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
            - header as a unicode string,
            - data encoded in JSON.

        :return: a tuple with header and body
        """
        return self.socket.recv_string(), self.socket.recv_json()


class InternalEventPublisher(object):
    """ This class is the wrapper of the PyZmq socket that publishes the events to the Supvisors instances.

    Attributes are:
        - identifier: the identifier of the Supvisors instance where this process is running,
        - socket: the ZeroMQ socket with a PUBLISH pattern, bound on the internal_port defined
          in the ['supvisors'] section of the Supervisor configuration file.
    """

    def __init__(self, instance: SupvisorsInstanceId, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param instance: the local Supvisors attributes
        :param logger: the Supvisors logger
        """
        # keep local identifier
        self.identifier = instance.identifier
        # create ZMQ socket
        self.socket = ZmqContext.socket(zmq.PUB)
        url = f'tcp://*:{instance.internal_port}'
        logger.debug(f'InternalEventPublisher: binding {url}')
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
        self.socket.send_pyobj((InternalEventHeaders.TICK.value, (self.identifier, payload)))

    def forward_event(self, event: Tuple[int, Tuple[str, Payload]]) -> None:
        """ Forward the event with PyZmq.

        :param event: the event to publish
        :return: None
        """
        self.socket.send_pyobj(event)


class InternalEventSubscriber(object):
    """ Class for subscription to Listener events.

    Attributes:
        - port: the port number used for internal events,
        - socket: the PyZMQ subscriber.
    """

    def __init__(self, instances: Dict[str, SupvisorsInstanceId], logger: Logger):
        """ Initialization of the attributes.

        :param instances: the Supvisors attributes of the publishing Supvisors instances
        :param logger: the Supvisors logger
        """
        # keep the references in case of disconnection is requested
        self.instances = instances
        self.socket = ZmqContext.socket(zmq.SUB)
        # connect all Supvisors instances
        for instance in instances.values():
            url = f'tcp://{instance.host_name}:{instance.internal_port}'
            logger.debug(f'InternalEventSubscriber: connecting {url}')
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

    def disconnect(self, identifiers: NameList) -> None:
        """ This method disconnects from the PyZmq socket all Supvisors instances declared in parameter.

        :param identifiers: the identifiers of the Supvisors instances to disconnect from the subscriber socket
        :return: None
        """
        for identifier in identifiers:
            instance = self.instances[identifier]
            self.socket.disconnect(f'tcp://{instance.host_name}:{instance.internal_port}')


class RequestPuller(object):
    """ Class for pulling deferred XML-RPC.

    Attributes:
        - socket: the PyZMQ puller.

    As it uses an inproc transport, this implies the following conditions:
        - the RequestPusher instance and the RequestPuller instance MUST share the same ZMQ context,
        - the RequestPusher instance MUST be created before the RequestPuller instance.
    """

    def __init__(self, logger: Logger) -> None:
        """ Initialization of the attributes. """
        self.socket = ZmqContext.socket(zmq.PULL)
        url = 'inproc://' + INPROC_NAME
        logger.debug(f'RequestPuller: connecting {url}')
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
        - logger: a reference to the Supvisors logger ;
        - identifier: the identifier of the local Supvisors instance ;
        - socket: the PyZMQ pusher.

    As it uses an inproc transport, this implies the following conditions:
        - the RequestPusher instance and the RequestPuller instance MUST share the same ZMQ context,
        - the RequestPusher instance MUST be created before the RequestPuller instance.
    """

    MessageType = Union[DeferredRequestHeaders, InternalEventHeaders]

    def __init__(self, identifier: str, logger: Logger) -> None:
        """ Initialization of the attributes.

        :param identifier: the identifier of the local Supvisors instance
        :param logger: the Supvisors logger
        """
        self.logger = logger
        self.identifier = identifier
        # create PyZmq PUSH socket
        self.socket = ZmqContext.socket(zmq.PUSH)
        url = f'inproc://{INPROC_NAME}'
        self.logger.debug(f'RequestPusher: binding {url}')
        self.socket.bind(url)

    def close(self):
        """ Close the PyZmq socket.

        :return: None
        """
        self.socket.close(ZMQ_LINGER)

    def send_message(self, header: MessageType, body: Tuple) -> None:
        """ Send request to check authorization to deal with the Supvisors instance.

        :param header: the message type
        :param body: the payload to send
        :return: None
        """
        self.logger.trace(f'RequestPusher.send_message: header={header.name}')
        try:
            self.socket.send_pyobj((header.value, body), zmq.NOBLOCK)
        except zmq.error.Again:
            self.logger.error(f'RequestPusher.send_message: failed to send message {header.name}')

    # deferred publications
    def send_tick_event(self, payload: Payload) -> None:
        """ Publish the tick event with PyZmq.

        :param payload: the tick to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.TICK, (self.identifier, payload))

    def send_process_state_event(self, payload: Payload) -> None:
        """ Publish the process state event with PyZmq.

        :param payload: the process state to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS, (self.identifier, payload))

    def send_process_added_event(self, payload: Payload) -> None:
        """ Publish the process added event with PyZmq.

        :param payload: the process added to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS_ADDED, (self.identifier, payload))

    def send_process_removed_event(self, payload: Payload) -> None:
        """ Publish the process removed event with PyZmq.

        :param payload: the process removed to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.PROCESS_REMOVED, (self.identifier, payload))

    def send_statistics(self, payload: Payload) -> None:
        """ Publish the statistics with PyZmq.

        :param payload: the statistics to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.STATISTICS, (self.identifier, payload))

    def send_state_event(self, payload: Payload) -> None:
        """ Publish the Master state event with PyZmq.

        :param payload: the Supvisors state to publish
        :return: None
        """
        self.send_message(InternalEventHeaders.STATE, (self.identifier, payload))

    # deferred requests
    def send_check_instance(self, identifier: str) -> None:
        """ Send request to check authorization to deal with the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance to check
        :return: None
        """
        self.send_message(DeferredRequestHeaders.CHECK_INSTANCE, (identifier,))

    def send_isolate_instances(self, identifiers: NameList) -> None:
        """ Send request to isolate instances.

        :param identifiers: the identifiers of the Supvisors instances to isolate
        :return: None
        """
        self.send_message(DeferredRequestHeaders.ISOLATE_INSTANCES, tuple(identifiers))

    def send_start_process(self, identifier: str, namespec: str, extra_args: str) -> None:
        """ Send request to start process.

        :param identifier: the identifier of the Supvisors instance where the process has to be started
        :param namespec: the process namespec
        :param extra_args: the additional arguments to be passed to the command line
        :return: None
        """
        self.send_message(DeferredRequestHeaders.START_PROCESS, (identifier, namespec, extra_args))

    def send_stop_process(self, identifier: str, namespec: str) -> None:
        """ Send request to stop process.

        :param identifier: the identifier of the Supvisors instance where the process has to be stopped
        :param namespec: the process namespec
        :return: None
        """
        self.send_message(DeferredRequestHeaders.STOP_PROCESS, (identifier, namespec))

    def send_restart(self, identifier: str):
        """ Send request to restart a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be restarted
        :return: None
        """
        self.send_message(DeferredRequestHeaders.RESTART, (identifier,))

    def send_shutdown(self, identifier: str):
        """ Send request to shutdown a Supervisor.

        :param identifier: the identifier of the Supvisors instance where Supvisors has to be shut down
        :return: None
        """
        self.send_message(DeferredRequestHeaders.SHUTDOWN, (identifier,))

    def send_restart_sequence(self, identifier: str):
        """ Send request to trigger the DEPLOYMENT phase.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.send_message(DeferredRequestHeaders.RESTART_SEQUENCE, (identifier,))

    def send_restart_all(self, identifier: str):
        """ Send request to restart Supvisors.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.send_message(DeferredRequestHeaders.RESTART_ALL, (identifier,))

    def send_shutdown_all(self, identifier: str):
        """ Send request to shutdown Supvisors.

        :param identifier: the Master Supvisors instance
        :return: None
        """
        self.send_message(DeferredRequestHeaders.SHUTDOWN_ALL, (identifier,))


class SupervisorZmq(object):
    """ Class for PyZmq context and sockets used from the Supervisor thread.
    This instance owns the PyZmq context that is shared between the Supervisor thread and the Supvisors thread. """

    def __init__(self, supvisors: Any) -> None:
        """ Create the sockets.

        :param supvisors: the Supvisors global structure
        """
        self.publisher = EventPublisher(supvisors.supvisors_mapper.local_instance, supvisors.logger)
        self.pusher = RequestPusher(supvisors.supvisors_mapper.local_identifier, supvisors.logger)

    def close(self) -> None:
        """ Close the sockets.

        :return: None
        """
        self.pusher.close()
        self.publisher.close()


class SupvisorsZmq(object):
    """ Class for PyZmq context and sockets used from the Supvisors thread. """

    # timeout for polling in milliseconds
    POLL_TIMEOUT = 500

    # types for annotations
    PollResult = Mapping[Any, int]
    SupvisorsSockets = Union[InternalEventSubscriber, RequestPuller]

    def __init__(self, supvisors: Any) -> None:
        """ Create the sockets and the poller.
        The Supervisor logger cannot be used here (not thread-safe).

        :param supvisors: the Supvisors global structure
        """
        # create zmq sockets
        self.publisher = InternalEventPublisher(supvisors.supvisors_mapper.local_instance, supvisors.logger)
        self.subscriber = InternalEventSubscriber(supvisors.supvisors_mapper.instances, supvisors.logger)
        self.puller = RequestPuller(supvisors.logger)
        # create poller
        self.poller = zmq.Poller()
        # register sockets to poller
        self.poller.register(self.subscriber.socket, zmq.POLLIN)
        self.poller.register(self.puller.socket, zmq.POLLIN)

    def close(self) -> None:
        """ Close the poller and the sockets.

        :return: None
        """
        # unregister sockets from poller
        self.poller.unregister(self.puller.socket)
        self.poller.unregister(self.subscriber.socket)
        # close sockets
        self.puller.close()
        self.subscriber.close()
        self.publisher.close()

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
        return SupvisorsZmq.check_socket(self.subscriber, poll_result)

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

    def disconnect_subscriber(self, identifiers: NameList) -> None:
        """ Disconnect the Supvisors instances from the subscription socket.

        :param identifiers: the identifiers of the Supvisors instances to disconnect
        :return: None
        """
        self.subscriber.disconnect(identifiers)
