#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2023 Julien LE CLEACH
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

import socket
import time
from unittest.mock import call

import pytest

pytest.importorskip('websockets', reason='cannot test as optional websockets is not installed')

from supvisors.client.wssubscriber import SupvisorsWsEventInterface
from supvisors.external_com.supvisorswebsocket import *
from supvisors.ttypes import EventHeaders


@pytest.fixture
def publisher(supvisors):
    test_publisher = WsEventPublisher(supvisors.mapper.local_instance, supvisors.logger)
    yield test_publisher
    test_publisher.close()


@pytest.fixture
def subscriber(mocker, supvisors):
    test_subscriber = SupvisorsWsEventInterface('localhost', supvisors.options.event_port, supvisors.logger)
    mocker.patch.object(test_subscriber, 'on_receive')
    # do NOT start the thread to let subscriptions happen
    yield test_subscriber
    test_subscriber.stop()


@pytest.fixture
def real_subscriber(supvisors):
    test_subscriber = SupvisorsWsEventInterface('localhost', supvisors.options.event_port, supvisors.logger)
    test_subscriber.subscribe_all()
    yield test_subscriber
    test_subscriber.stop()


supvisors_payload = {'state': 'running', 'version': '1.0'}
instance_payload = {'state': 'silent', 'identifier': 'cliche01', 'date': 1234}
application_payload = {'state': 'starting', 'name': 'supvisors'}
event_payload = {'state': 20, 'name': 'plugin', 'group': 'supvisors', 'now': 1230}
process_payload = {'state': 'running', 'process_name': 'plugin', 'application_name': 'supvisors', 'date': 1230}
hstats_payload = {'identifier': '10.0.0.1', 'period': 5.2, 'uptime': 1230, 'cpu': [28.3]}
pstats_payload = {'identifier': '10.0.0.1', 'namespec': 'dummy_proc', 'period': 5.2, 'uptime': 1230, 'cpu': [28.3]}


def publish_all(publisher):
    """ Send all kind of expected messages. """
    publisher.send_supvisors_status(supvisors_payload)
    publisher.send_instance_status(instance_payload)
    publisher.send_application_status(application_payload)
    publisher.send_process_event('local_identifier', event_payload)
    publisher.send_process_status(process_payload)
    publisher.send_host_statistics(hstats_payload)
    publisher.send_process_statistics(pstats_payload)


def wait_thread_alive(thr: AsyncEventThread, max_time: int = 5) -> bool:
    """ Wait for publisher to be alive and connected to one client (5 seconds max by default). """
    nb_tries = max_time * 2
    while nb_tries > 0 and not (thr.loop and thr.loop.is_running()):
        time.sleep(0.5)
        nb_tries -= 1
    return thr.loop and thr.loop.is_running()


def check_subscription(subscriber: SupvisorsWsEventInterface, publisher: WsEventPublisher,
                       supvisors_subscribed=False, instance_subscribed=False,
                       application_subscribed=False, event_subscribed=False, process_subscribed=False,
                       hstats_subscribed=False, pstats_subscribed=False):
    """ The method tests the emission and reception of all status, depending on their subscription status. """
    subscriber.start()
    # give time to the websocket client to connect the server
    assert wait_thread_alive(publisher.thread)
    assert wait_thread_alive(subscriber.thread)
    # publish and receive
    time.sleep(1)
    publish_all(publisher)
    # give time to the subscriber to receive data
    time.sleep(2)
    # get the results list expected
    results = []
    if supvisors_subscribed:
        results.append(call(EventHeaders.SUPVISORS.value, supvisors_payload))
    if instance_subscribed:
        results.append(call(EventHeaders.INSTANCE.value, instance_payload))
    if application_subscribed:
        results.append(call(EventHeaders.APPLICATION.value, application_payload))
    if event_subscribed:
        payload = dict(event_payload, **{'identifier': 'local_identifier'})
        results.append(call(EventHeaders.PROCESS_EVENT.value, payload))
    if process_subscribed:
        results.append(call(EventHeaders.PROCESS_STATUS.value, process_payload))
    if hstats_subscribed:
        results.append(call(EventHeaders.HOST_STATISTICS.value, hstats_payload))
    if pstats_subscribed:
        results.append(call(EventHeaders.PROCESS_STATISTICS.value, pstats_payload))
    # check the results
    assert subscriber.on_receive.call_args_list == results
    subscriber.on_receive.reset_mock()
    # stop and reset the subscriber
    subscriber.stop()
    subscriber.reset()


def test_external_publish_subscribe(supvisors):
    """ Test the opening and closing of the Websocket server/client used in the event interface of Supvisors. """
    # get event port
    port = supvisors.options.event_port
    # create publisher and subscriber
    publisher = WsEventPublisher(supvisors.mapper.local_instance, supvisors.logger)
    subscriber = SupvisorsWsEventInterface('localhost', port, supvisors.logger)
    subscriber.start()
    assert wait_thread_alive(publisher.thread)
    assert wait_thread_alive(subscriber.thread)
    # sleep a bit to give time to hit the reception timeout
    time.sleep(ASYNC_TIMEOUT)
    # check the server side
    assert websocket_clients
    # check the client side
    assert subscriber.headers == set()
    # close the server
    publisher.close()
    # check the server side
    assert not publisher.thread.is_alive()
    assert not publisher.thread.loop
    # stop the client
    subscriber.stop()
    # check the client side
    assert not subscriber.thread.is_alive()
    assert not subscriber.thread.loop


def test_no_subscription(publisher, subscriber):
    """ Test the non-reception of messages when subscription is not set. """
    # at this stage, no subscription has been set so nothing should be received
    check_subscription(subscriber, publisher)


def test_subscription_supvisors_status(publisher, subscriber):
    """ Test the reception of Supvisors status messages when related subscription is set. """
    # subscribe to Supvisors status only
    subscriber.subscribe_supvisors_status()
    check_subscription(subscriber, publisher, supvisors_subscribed=True)
    # unsubscribe from Supvisors status
    subscriber.unsubscribe_supvisors_status()
    check_subscription(subscriber, publisher)


def test_subscription_instance_status(publisher, subscriber):
    """ Test the reception of Instance status messages when related subscription is set. """
    # subscribe to Instance status only
    subscriber.subscribe_instance_status()
    check_subscription(subscriber, publisher, instance_subscribed=True)
    # unsubscribe from Instance status
    subscriber.unsubscribe_instance_status()
    check_subscription(subscriber, publisher)


def test_subscription_application_status(publisher, subscriber):
    """ Test the reception of Application status messages when related subscription is set. """
    # subscribe to Application status only
    subscriber.subscribe_application_status()
    check_subscription(subscriber, publisher, application_subscribed=True)
    # unsubscribe from Application status
    subscriber.unsubscribe_application_status()
    check_subscription(subscriber, publisher)


def test_subscription_process_event(publisher, subscriber):
    """ Test the reception of Process event messages when related subscription is set. """
    # subscribe to Process event only
    subscriber.subscribe_process_event()
    check_subscription(subscriber, publisher, event_subscribed=True)
    # unsubscribe from Process event
    subscriber.unsubscribe_process_event()
    check_subscription(subscriber, publisher)


def test_subscription_process_status(publisher, subscriber):
    """ Test the reception of Process status messages when related subscription is set. """
    # subscribe to Process status only
    subscriber.subscribe_process_status()
    check_subscription(subscriber, publisher, process_subscribed=True)
    # unsubscribe from Process status
    subscriber.unsubscribe_process_status()
    check_subscription(subscriber, publisher)


def test_subscription_host_statistics(publisher, subscriber):
    """ Test the reception of Host statistics messages when related subscription is set. """
    # subscribe to Host statistics only
    subscriber.subscribe_host_statistics()
    check_subscription(subscriber, publisher, hstats_subscribed=True)
    # unsubscribe from Host statistics
    subscriber.unsubscribe_host_statistics()
    check_subscription(subscriber, publisher)


def test_subscription_process_statistics(publisher, subscriber):
    """ Test the reception of Process statistics messages when related subscription is set. """
    # subscribe to Process statistics only
    subscriber.subscribe_process_statistics()
    check_subscription(subscriber, publisher, pstats_subscribed=True)
    # unsubscribe from Process statistics
    subscriber.unsubscribe_process_statistics()
    check_subscription(subscriber, publisher)


def test_subscription_all_status(publisher, subscriber):
    """ Test the reception of all status messages when related subscription is set. """
    # subscribe to every status
    subscriber.subscribe_all()
    check_subscription(subscriber, publisher,
                       supvisors_subscribed=True, instance_subscribed=True,
                       application_subscribed=True, event_subscribed=True, process_subscribed=True,
                       hstats_subscribed=True, pstats_subscribed=True)
    # unsubscribe all
    subscriber.unsubscribe_all()
    check_subscription(subscriber, publisher)


def test_subscription_multiple_status(publisher, subscriber):
    """ Test the reception of multiple status messages when related subscription is set. """
    # subscribe to Application and Process Event
    subscriber.subscribe_application_status()
    subscriber.subscribe_process_event()
    check_subscription(subscriber, publisher, application_subscribed=True, event_subscribed=True)
    # set subscription to Instance and Process Status
    subscriber.reset()
    subscriber.unsubscribe_application_status()
    subscriber.unsubscribe_process_event()
    subscriber.subscribe_process_status()
    subscriber.subscribe_instance_status()
    check_subscription(subscriber, publisher, instance_subscribed=True, process_subscribed=True)
    # add subscription to Supvisors Status and remove process
    subscriber.reset()
    subscriber.subscribe_supvisors_status()
    subscriber.unsubscribe_process_status()
    check_subscription(subscriber, publisher, supvisors_subscribed=True, instance_subscribed=True)
    # add subscription to Statistics and remove Supvisors Status
    subscriber.reset()
    subscriber.unsubscribe_supvisors_status()
    subscriber.subscribe_host_statistics()
    subscriber.subscribe_process_statistics()
    check_subscription(subscriber, publisher, instance_subscribed=True, hstats_subscribed=True, pstats_subscribed=True)
    # unsubscribe all
    subscriber.reset()
    subscriber.unsubscribe_instance_status()
    subscriber.unsubscribe_host_statistics()
    subscriber.unsubscribe_process_statistics()
    check_subscription(subscriber, publisher)


# testing exception cases and lines hard to hit (by line number)
@pytest.mark.asyncio
async def test_serve_failed():
    """ Test the reception of a message with unknown header.
    The aim is to hit the lines 63-65 in ws_server.
    Checked ok with debugger.
    """
    # bind a socket to port 65100
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 65100))
    # create stop event
    stop_event = asyncio.Event()

    async def test_task():
        await asyncio.sleep(2.0)
        # the websockets server creation should have failed at least once
        # set the stop event
        stop_event.set()

    # start the websockets server using a port already bound
    await asyncio.gather(ws_server(stop_event, '', 65100), test_task())
    # close the socket on exit
    sock.close()


@pytest.mark.asyncio
async def test_wait_tasks():
    """ Test the reception of a message with unknown header.
    The aim is to hit the line 78 in ws_server.
    Checked ok with debugger.
    """
    # create stop event
    stop_event = asyncio.Event()

    async def stop_task():
        await asyncio.sleep(2.0)
        # the websockets server should be created
        # set the stop event
        stop_event.set()
        # pause this task to force ws_server to wait for it
        await asyncio.sleep(2.0)

    await asyncio.gather(ws_server(stop_event, '', 65100), stop_task())


def test_unknown_message(mocker, publisher, real_subscriber):
    """ Test the reception of a message with unknown header.
    The aim is to hit the lines 223-224 in WsEventSubscriber.mainloop.
    Checked ok with debugger.
    """
    # give time to the websocket client to connect the server
    real_subscriber.start()
    assert wait_thread_alive(real_subscriber.thread)
    # mock the on_xxx methods
    mocked_ons = [mocker.patch.object(real_subscriber, method_name)
                  for method_name in ['on_supvisors_status', 'on_instance_status', 'on_application_status',
                                      'on_process_event', 'on_process_status',
                                      'on_host_statistics', 'on_process_statistics']]
    # publish a message of each type
    time.sleep(1)
    publish_all(publisher)
    time.sleep(2)
    # check that no NotImplementedError exception is raised and all on_xxx called
    for mock in mocked_ons:
        assert mock.call_count == 1
        mock.reset_mock()
    # now send an unexpected event
    websockets.broadcast(websocket_clients, json.dumps(('dummy header', 'dummy body')))
    # check that no on_xxx has been called
    time.sleep(2)
    assert all(not mock.called for mock in mocked_ons)


def test_close_server(real_subscriber, publisher):
    """ Test the server closure while a client is connected.
    The aim is to hit the lines 226-227 in WsEventSubscriber.mainloop.
    Checked ok with debugger.
    """
    # give time to the websocket client to connect the server
    real_subscriber.start()
    assert wait_thread_alive(real_subscriber.thread)
    # the publisher will be stopped just after all the publications
    # default websocket ping is 20 seconds
    publish_all(publisher)
    publisher.close()
    time.sleep(30)
    # the ConnectionClosed handling should have been hit
