#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import pytest

from supvisors.supvisorszmq import *
from supvisors.utils import DeferredRequestHeaders
from time import sleep
from unittest.mock import call, Mock


def test_internal_publish_subscribe(supvisors):
    """ Test the ZeroMQ publish-subscribe sockets used internally in Supvisors. """
    # create publisher and subscriber
    publisher = InternalEventPublisher(supvisors.supvisors_mapper.local_instance, supvisors.logger)
    subscriber = InternalEventSubscriber(supvisors.supvisors_mapper.instances, supvisors.logger)
    # check that the ZMQ sockets are ready
    assert not publisher.socket.closed
    assert not subscriber.socket.closed
    # close the sockets
    publisher.close()
    subscriber.close()
    # check that the ZMQ socket are closed
    assert publisher.socket.closed
    assert subscriber.socket.closed


def test_external_publish_subscribe(supvisors):
    """ Test the ZeroMQ publish-subscribe sockets used in the event interface of Supvisors. """
    # get event port
    port = supvisors.options.event_port
    # create publisher and subscriber
    publisher = EventPublisher(supvisors.supvisors_mapper.local_instance, supvisors.logger)
    subscriber = EventSubscriber(zmq.Context.instance(), port, supvisors.logger)
    # check that the ZMQ sockets are ready
    assert not publisher.socket.closed
    assert not subscriber.socket.closed
    # close the sockets
    publisher.close()
    subscriber.close()
    # check that the ZMQ socket are closed
    assert publisher.socket.closed
    assert subscriber.socket.closed


def test_internal_pusher_puller(supvisors):
    """ Test the ZeroMQ push-pull sockets used internally in Supvisors. """
    # create publisher and subscriber
    pusher = RequestPusher(supvisors.supvisors_mapper.local_identifier, supvisors.logger)
    puller = RequestPuller(supvisors.logger)
    # check that the ZMQ sockets are ready
    assert not pusher.socket.closed
    assert not puller.socket.closed
    # close the sockets
    pusher.close()
    puller.close()
    # check that the ZMQ socket are closed
    assert pusher.socket.closed
    assert puller.socket.closed


@pytest.fixture
def internal_publisher(supvisors):
    test_publisher = InternalEventPublisher(supvisors.supvisors_mapper.local_instance, supvisors.logger)
    yield test_publisher
    test_publisher.close()
    sleep(0.5)


@pytest.fixture
def internal_subscriber(supvisors):
    test_subscriber = InternalEventSubscriber(supvisors.supvisors_mapper.instances, supvisors.logger)
    test_subscriber.socket.setsockopt(zmq.RCVTIMEO, 1000)
    # publisher does not wait for subscriber clients to work, so give some time for connections
    sleep(0.5)
    yield test_subscriber
    test_subscriber.close()
    sleep(0.5)


def internal_subscriber_receive(internal_subscriber):
    """ This method performs a checked reception on the subscriber. """
    internal_subscriber.socket.poll(1000)
    return internal_subscriber.receive()


def test_disconnection(supvisors, internal_publisher, internal_subscriber):
    """ Test the disconnection of subscribers. """
    # get the local identifier
    local_identifier = supvisors.supvisors_mapper.local_identifier
    # test remote disconnection
    identifier = next(identifier for identifier in supvisors.supvisors_mapper.instances
                      if identifier != local_identifier)
    internal_subscriber.disconnect([identifier])
    # send a tick event from the local publisher
    payload = {'date': 1000}
    internal_publisher.send_tick_event(payload)
    # check the reception of the tick event
    msg = internal_subscriber_receive(internal_subscriber)
    assert msg == (InternalEventHeaders.TICK.value, (local_identifier, payload))
    # test local disconnection
    internal_subscriber.disconnect([local_identifier])
    # send a tick event from the local publisher
    internal_publisher.send_tick_event(payload)
    # check the non-reception of the tick event
    with pytest.raises(zmq.Again):
        internal_subscriber.receive()


def test_publish_tick_event(supvisors, internal_publisher, internal_subscriber):
    """ Test the publication and subscription of the messages. """
    # get the local address
    local_node_name = supvisors.supvisors_mapper.local_identifier
    # send a tick event
    payload = {'date': 1000}
    internal_publisher.send_tick_event(payload)
    # check the reception of the tick event
    msg = internal_subscriber_receive(internal_subscriber)
    assert msg == (InternalEventHeaders.TICK.value, (local_node_name, payload))


def test_process_state_event(supvisors, internal_publisher, internal_subscriber):
    """ Test the publication and subscription of the process state events. """
    # get the local address
    local_node_name = supvisors.supvisors_mapper.local_identifier
    # send a process event
    message = (InternalEventHeaders.PROCESS.value,
               (local_node_name, {'name': 'dummy_program', 'state': 'running'}))
    internal_publisher.forward_event(message)
    # check the reception of the process event
    received_message = internal_subscriber_receive(internal_subscriber)
    assert received_message == message


def test_process_added_event(supvisors, internal_publisher, internal_subscriber):
    """ Test the publication and subscription of the process added events. """
    # get the local address
    local_node_name = supvisors.supvisors_mapper.local_identifier
    # send a process event
    message = (InternalEventHeaders.PROCESS_ADDED.value,
               (local_node_name, {'name': 'dummy_program', 'state': 'running'}))
    internal_publisher.forward_event(message)
    # check the reception of the process event
    received_message = internal_subscriber_receive(internal_subscriber)
    assert received_message == message


def test_process_removed_event(supvisors, internal_publisher, internal_subscriber):
    """ Test the publication and subscription of the process removed events. """
    # get the local address
    local_node_name = supvisors.supvisors_mapper.local_identifier
    # send a process event
    message = (InternalEventHeaders.PROCESS_ADDED.value,
               (local_node_name, {'name': 'dummy_program', 'state': 'running'}))
    internal_publisher.forward_event(message)
    # check the reception of the process event
    received_message = internal_subscriber_receive(internal_subscriber)
    assert received_message == message


def test_statistics(supvisors, internal_publisher, internal_subscriber):
    """ Test the publication and subscription of the statistics messages. """
    # get the local address
    local_node_name = supvisors.supvisors_mapper.local_identifier
    # send a statistics event
    message = (InternalEventHeaders.STATISTICS.value,
               (local_node_name, {'cpu': 15, 'mem': 5, 'io': (1234, 4321)}))
    internal_publisher.forward_event(message)
    # check the reception of the statistics event
    received_message = internal_subscriber_receive(internal_subscriber)
    assert received_message == message


def test_state_event(supvisors, internal_publisher, internal_subscriber):
    """ Test the publication and subscription of the operational event. """
    # get the local node
    local_node_name = supvisors.supvisors_mapper.local_identifier
    # send a process event
    message = (InternalEventHeaders.STATE.value,
               (local_node_name, {'statecode': 10, 'statename': 'running'}))
    internal_publisher.forward_event(message)
    # check the reception of the process event
    received_message = internal_subscriber_receive(internal_subscriber)
    assert received_message == message


@pytest.fixture
def pusher(supvisors):
    test_pusher = RequestPusher(supvisors.supvisors_mapper.local_identifier, supvisors.logger)
    yield test_pusher
    test_pusher.close()
    sleep(0.5)


@pytest.fixture
def puller(supvisors):
    test_puller = RequestPuller(supvisors.logger)
    # socket configuration is meant to be blocking
    # however, a failure would block the unit test, so a timeout is set for emission and reception
    test_puller.socket.setsockopt(zmq.SNDTIMEO, 1000)
    test_puller.socket.setsockopt(zmq.RCVTIMEO, 1000)
    yield test_puller
    test_puller.close()
    sleep(0.5)


def _test_push_event(mocker, pusher: RequestPusher, puller: RequestPuller, fct, event_type: InternalEventHeaders):
    """ The method tests that the TICK event is sent and received correctly through PyZmq PUSH / PULL. """
    local_identifier = pusher.identifier
    payload = {'payload': 1234}
    fct(payload)
    request = puller.receive()
    assert request == (event_type.value, (local_identifier, payload))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    fct(payload)
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    fct(payload)


def test_push_tick_event(mocker, pusher, puller):
    """ The method tests that the TICK event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_tick_event, InternalEventHeaders.TICK)


def test_push_process_state_event(mocker, pusher, puller):
    """ The method tests that the PROCESS event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_process_state_event, InternalEventHeaders.PROCESS)


def test_push_process_added_event(mocker, pusher, puller):
    """ The method tests that the PROCESS_ADDED event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_process_added_event, InternalEventHeaders.PROCESS_ADDED)


def test_push_process_removed_event(mocker, pusher, puller):
    """ The method tests that the PROCESS_REMOVED event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_process_removed_event, InternalEventHeaders.PROCESS_REMOVED)


def test_push_process_disability_event(mocker, pusher, puller):
    """ The method tests that the PROCESS_DISABILITY event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_process_disability_event,
                     InternalEventHeaders.PROCESS_DISABILITY)


def test_push_statistics_event(mocker, pusher, puller):
    """ The method tests that the STATISTICS event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_statistics, InternalEventHeaders.STATISTICS)


def test_push_state_event(mocker, pusher, puller):
    """ The method tests that the STATE event is sent and received correctly through PyZmq PUSH / PULL. """
    _test_push_event(mocker, pusher, puller, pusher.send_state_event, InternalEventHeaders.STATE)


def test_check_node(mocker, pusher, puller):
    """ The method tests that the 'Check Address' request is sent and received correctly. """
    pusher.send_check_instance('10.0.0.1')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.CHECK_INSTANCE.value, ('10.0.0.1',))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_check_instance('10.0.0.1')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_check_instance('10.0.0.1')


def test_isolate_nodes(mocker, pusher, puller):
    """ The method tests that the 'Isolate Nodes' request is sent and received correctly. """
    pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
    request = puller.receive()
    assert request == (DeferredRequestHeaders.ISOLATE_INSTANCES.value, ('10.0.0.1', '10.0.0.2'))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])


def test_start_process(mocker, pusher, puller):
    """ The method tests that the 'Start Process' request is sent and received correctly. """
    pusher.send_start_process('10.0.0.1', 'application:program', '-extra arguments')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.START_PROCESS.value,
                       ('10.0.0.1', 'application:program', '-extra arguments'))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_start_process('10.0.0.1', 'application:program', '-extra arguments')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_start_process('10.0.0.1', 'application:program', '-extra arguments')


def test_stop_process(mocker, pusher, puller):
    """ The method tests that the 'Stop Process' request is sent and received correctly. """
    pusher.send_stop_process('10.0.0.1', 'application:program')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.STOP_PROCESS.value, ('10.0.0.1', 'application:program'))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_stop_process('10.0.0.1', 'application:program')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_stop_process('10.0.0.1', 'application:program')


def test_restart(mocker, pusher, puller):
    """ The method tests that the 'Restart' request is sent and received correctly. """
    pusher.send_restart('10.0.0.1')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.RESTART.value, ('10.0.0.1',))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_restart('10.0.0.1')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_restart('10.0.0.1')


def test_shutdown(mocker, pusher, puller):
    """ The method tests that the 'Shutdown' request is sent and received correctly. """
    pusher.send_shutdown('10.0.0.1')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.SHUTDOWN.value, ('10.0.0.1',))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_shutdown('10.0.0.1')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_shutdown('10.0.0.1')


def test_restart_sequence(mocker, pusher, puller):
    """ The method tests that the 'RestartSequence' request is sent and received correctly. """
    pusher.send_restart_sequence('10.0.0.1')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.RESTART_SEQUENCE.value, ('10.0.0.1',))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_restart_sequence('10.0.0.1')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_restart_sequence('10.0.0.1')


def test_restart_all(mocker, pusher, puller):
    """ The method tests that the 'RestartAll' request is sent and received correctly. """
    pusher.send_restart_all('10.0.0.1')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.RESTART_ALL.value, ('10.0.0.1',))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_restart_all('10.0.0.1')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_restart_all('10.0.0.1')


def test_shutdown_all(mocker, pusher, puller):
    """ The method tests that the 'ShutdownAll' request is sent and received correctly. """
    pusher.send_shutdown_all('10.0.0.1')
    request = puller.receive()
    assert request == (DeferredRequestHeaders.SHUTDOWN_ALL.value, ('10.0.0.1',))
    # test that the pusher socket is not blocking
    mocker.patch.object(pusher.socket, 'send_pyobj', side_effect=zmq.error.Again)
    pusher.send_shutdown_all('10.0.0.1')
    # test that absence of puller does not block the pusher or raise any exception
    puller.close()
    pusher.send_shutdown_all('10.0.0.1')


@pytest.fixture
def publisher(supvisors):
    test_publisher = EventPublisher(supvisors.supvisors_mapper.local_instance, supvisors.logger)
    yield test_publisher
    test_publisher.close()
    sleep(0.5)


@pytest.fixture
def subscriber(supvisors):
    test_subscriber = EventSubscriber(zmq.Context.instance(), supvisors.options.event_port, supvisors.logger)
    # WARN: this subscriber does not include a subscription
    # when using a subscription, use a time sleep to give time to PyZMQ to handle it
    # sleep(0.5)
    # WARN: socket configuration is meant to be blocking
    # however, a failure would block the unit test, so a timeout is set for reception
    test_subscriber.socket.setsockopt(zmq.RCVTIMEO, 1000)
    yield test_subscriber
    test_subscriber.close()
    sleep(0.5)


def check_reception(subscriber, header=None, data=None):
    """ The method tests that the message is received correctly or not received at all. """
    if header and data:
        # check that subscriber receives the message
        msg = subscriber.receive()
        assert msg == (header, data)
    else:
        # check the non-reception of the Supvisors status
        with pytest.raises(zmq.Again):
            subscriber.receive()


def check_supvisors_status(subscriber, publisher, subscribed):
    """ The method tests the emission and reception of a Supvisors status, depending on the subscription status. """
    supvisors_payload = {'state': 'running', 'version': '1.0'}
    publisher.send_supvisors_status(supvisors_payload)
    if subscribed:
        check_reception(subscriber, EventHeaders.SUPVISORS, supvisors_payload)
    else:
        check_reception(subscriber)


def check_instance_status(subscriber, publisher, subscribed):
    """ The method tests the emission and reception of an node status, depending on the subscription status. """
    node_payload = {'state': 'silent', 'identifier': 'cliche01', 'date': 1234}
    publisher.send_instance_status(node_payload)
    if subscribed:
        check_reception(subscriber, EventHeaders.INSTANCE, node_payload)
    else:
        check_reception(subscriber)


def check_application_status(subscriber, publisher, subscribed):
    """ The method tests the emission and reception of an Application status, depending on the subscription status. """
    application_payload = {'state': 'starting', 'name': 'supvisors'}
    publisher.send_application_status(application_payload)
    if subscribed:
        check_reception(subscriber, EventHeaders.APPLICATION, application_payload)
    else:
        check_reception(subscriber)


def check_process_event(subscriber, publisher, subscribed):
    """ The method tests the emission and reception of a Process status,  depending on the subscription status. """
    event_payload = {'state': 20, 'name': 'plugin', 'group': 'supvisors', 'now': 1230}
    publisher.send_process_event('local_identifier', event_payload)
    if subscribed:
        event_payload['identifier'] = 'local_identifier'
        check_reception(subscriber, EventHeaders.PROCESS_EVENT, event_payload)
    else:
        check_reception(subscriber)


def check_process_status(subscriber, publisher, subscribed):
    """ The method tests the emission and reception of a Process status, depending on the subscription status. """
    process_payload = {'state': 'running', 'process_name': 'plugin', 'application_name': 'supvisors', 'date': 1230}
    publisher.send_process_status(process_payload)
    if subscribed:
        check_reception(subscriber, EventHeaders.PROCESS_STATUS, process_payload)
    else:
        check_reception(subscriber)


def check_subscription(subscriber, publisher, supvisors_subscribed, address_subscribed,
                       application_subscribed, event_subscribed, process_subscribed):
    """ The method tests the emission and reception of all status, depending on their subscription status. """
    sleep(1)
    check_supvisors_status(subscriber, publisher, supvisors_subscribed)
    check_instance_status(subscriber, publisher, address_subscribed)
    check_application_status(subscriber, publisher, application_subscribed)
    check_process_event(subscriber, publisher, event_subscribed)
    check_process_status(subscriber, publisher, process_subscribed)


def test_no_subscription(publisher, subscriber):
    """ Test the non-reception of messages when subscription is not set. """
    # at this stage, no subscription has been set so nothing should be received
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_supvisors_status(publisher, subscriber):
    """ Test the reception of Supvisors status messages when related subscription is set. """
    # subscribe to Supvisors status only
    subscriber.subscribe_supvisors_status()
    check_subscription(subscriber, publisher, True, False, False, False, False)
    # unsubscribe from Supvisors status
    subscriber.unsubscribe_supvisors_status()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_node_status(publisher, subscriber):
    """ Test the reception of Address status messages when related subscription is set. """
    # subscribe to Address status only
    subscriber.subscribe_instance_status()
    check_subscription(subscriber, publisher, False, True, False, False, False)
    # unsubscribe from Address status
    subscriber.unsubscribe_instance_status()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_application_status(publisher, subscriber):
    """ Test the reception of Application status messages when related subscription is set. """
    # subscribe to Application status only
    subscriber.subscribe_application_status()
    check_subscription(subscriber, publisher, False, False, True, False, False)
    # unsubscribe from Application status
    subscriber.unsubscribe_application_status()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_process_event(publisher, subscriber):
    """ Test the reception of Process event messages when related subscription is set. """
    # subscribe to Process event only
    subscriber.subscribe_process_event()
    check_subscription(subscriber, publisher, False, False, False, True, False)
    # unsubscribe from Process event
    subscriber.unsubscribe_process_event()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_process_status(publisher, subscriber):
    """ Test the reception of Process status messages when related subscription is set. """
    # subscribe to Process status only
    subscriber.subscribe_process_status()
    check_subscription(subscriber, publisher, False, False, False, False, True)
    # unsubscribe from Process status
    subscriber.unsubscribe_process_status()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_all_status(publisher, subscriber):
    """ Test the reception of all status messages when related subscription is set. """
    # subscribe to every status
    subscriber.subscribe_all()
    check_subscription(subscriber, publisher, True, True, True, True, True)
    # unsubscribe all
    subscriber.unsubscribe_all()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_subscription_multiple_status(publisher, subscriber):
    """ Test the reception of multiple status messages when related subscription is set. """
    # subscribe to Application and Process Event
    subscriber.subscribe_application_status()
    subscriber.subscribe_process_event()
    check_subscription(subscriber, publisher, False, False, True, True, False)
    # set subscription to Node and Process Status
    subscriber.unsubscribe_application_status()
    subscriber.unsubscribe_process_event()
    subscriber.subscribe_process_status()
    subscriber.subscribe_instance_status()
    check_subscription(subscriber, publisher, False, True, False, False, True)
    # add subscription to Supvisors Status
    subscriber.subscribe_supvisors_status()
    check_subscription(subscriber, publisher, True, True, False, False, True)
    # unsubscribe all
    subscriber.unsubscribe_supvisors_status()
    subscriber.unsubscribe_instance_status()
    subscriber.unsubscribe_process_status()
    check_subscription(subscriber, publisher, False, False, False, False, False)


def test_supervisor_creation_closure(supvisors):
    """ Test the attributes created in SupervisorZmq constructor. """
    sockets = SupervisorZmq(supvisors)
    # test all attribute types
    assert isinstance(sockets.publisher, EventPublisher)
    assert not sockets.publisher.socket.closed
    assert isinstance(sockets.pusher, RequestPusher)
    assert not sockets.pusher.socket.closed
    # close the instance
    sockets.close()
    assert sockets.publisher.socket.closed
    assert sockets.pusher.socket.closed


def test_supvisors_creation_closure(supvisors):
    """ Test the attributes created in SupvisorsZmq constructor. """
    sockets = SupvisorsZmq(supvisors)
    # test all attribute types
    assert isinstance(sockets.publisher, InternalEventPublisher)
    assert not sockets.publisher.socket.closed
    assert isinstance(sockets.subscriber, InternalEventSubscriber)
    assert not sockets.subscriber.socket.closed
    assert isinstance(sockets.puller, RequestPuller)
    assert not sockets.puller.socket.closed
    assert sockets.puller.socket in sockets.poller._map
    assert sockets.subscriber.socket in sockets.poller._map
    # close the instance
    sockets.close()
    assert sockets.poller._map == {}
    assert sockets.publisher.socket.closed
    assert sockets.subscriber.socket.closed
    assert sockets.puller.socket.closed


def test_poll(supvisors):
    """ Test the poll method of the SupvisorsZmq class. """
    sockets = SupvisorsZmq(supvisors)
    assert sockets.poll() == {}


def test_check_puller(mocker, supvisors):
    """ Test the check_puller method of the SupvisorsZmq class. """
    mocked_check = mocker.patch('supvisors.supvisorszmq.SupvisorsZmq.check_socket', return_value='checked')
    sockets = SupvisorsZmq(supvisors)
    param = Mock()
    assert sockets.check_puller(param) == 'checked'
    assert mocked_check.call_args_list == [call(sockets.puller, param)]


def test_check_subscriber(mocker, supvisors):
    """ Test the check_subscriber method of the SupvisorsZmq class. """
    mocked_check = mocker.patch('supvisors.supvisorszmq.SupvisorsZmq.check_socket', return_value='checked')
    sockets = SupvisorsZmq(supvisors)
    param = Mock()
    assert sockets.check_subscriber(param) == 'checked'
    assert mocked_check.call_args_list == [call(sockets.subscriber, param)]


def test_check_socket(mocker, supvisors):
    """ Test the types of the attributes created. """
    mocker.patch('builtins.print')
    sockets = SupvisorsZmq(supvisors)
    # prepare context
    mocked_sockets = Mock(socket='socket', **{'receive.side_effect': ZMQError})
    # test with empty poll result
    poll_result = {}
    # test with socket not in poll result
    assert sockets.check_socket(mocked_sockets, poll_result) is None
    assert not mocked_sockets.receive.called
    # test with socket in poll result but with pollout tag
    poll_result = {'socket': zmq.POLLOUT}
    assert sockets.check_socket(mocked_sockets, poll_result) is None
    assert not mocked_sockets.receive.called
    # test with socket in poll result and with pollin tag
    # test exception
    poll_result = {'socket': zmq.POLLIN}
    assert sockets.check_socket(mocked_sockets, poll_result) is None
    assert mocked_sockets.receive.called
    mocked_sockets.receive.reset_mock()
    # test with socket in poll result and with pollin tag
    # test normal behaviour
    mocked_sockets.receive.side_effect = None
    mocked_sockets.receive.return_value = 'message'
    assert sockets.check_socket(mocked_sockets, poll_result) == 'message'
    assert mocked_sockets.receive.called


def test_disconnect_subscriber(mocker, supvisors):
    """ Test the types of the attributes created. """
    mocked_disconnect = mocker.patch('supvisors.supvisorszmq.InternalEventSubscriber.disconnect')
    sockets = SupvisorsZmq(supvisors)
    # test disconnect on unknown address
    sockets.disconnect_subscriber(['10.0.0.1'])
    assert mocked_disconnect.call_args_list == [call(['10.0.0.1'])]
