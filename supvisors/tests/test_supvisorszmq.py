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
from supvisors.ttypes import DeferredRequestHeaders
from time import sleep
from unittest.mock import call, Mock


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
        assert msg == (header.value, data)
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
