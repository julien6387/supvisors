#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2022 Julien LE CLEACH
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

import time
from unittest.mock import call, Mock

import pytest

from supvisors.external_com.eventinterface import *


@pytest.fixture
def zmq_import():
    return pytest.importorskip('zmq')


@pytest.fixture
def zmq_fail_import(mocker):
    """ Mock ImportError on optional pyzmq if installed to force testing. """
    mocker.patch.dict('sys.modules', {'zmq': None})


@pytest.fixture
def ws_import():
    return pytest.importorskip('websockets')


@pytest.fixture
def ws_fail_import(mocker):
    """ Mock ImportError on optional websockets if installed to force testing. """
    mocker.patch.dict('sys.modules', {'websockets': None})


def test_interface():
    """ Test the EventPublisherInterface abstract class. """
    intf = EventPublisherInterface()
    with pytest.raises(NotImplementedError):
        intf.close()
    with pytest.raises(NotImplementedError):
        intf.send_supvisors_status({})
    with pytest.raises(NotImplementedError):
        intf.send_instance_status({})
    with pytest.raises(NotImplementedError):
        intf.send_application_status({})
    with pytest.raises(NotImplementedError):
        intf.send_process_event('10.0.0.1', {})
    with pytest.raises(NotImplementedError):
        intf.send_process_status({})
    with pytest.raises(NotImplementedError):
        intf.send_host_statistics({})
    with pytest.raises(NotImplementedError):
        intf.send_process_statistics({})


def test_create_external_publisher_none(supvisors):
    """ Test the create_external_publisher function with no event link selected. """
    assert create_external_publisher(supvisors) is None


def test_create_external_publisher_zmq_fail(zmq_import, zmq_fail_import, supvisors):
    """ Test the create_external_publisher function with zmq event link but not installed. """
    supvisors.options.event_link = EventLinks.ZMQ
    assert create_external_publisher(supvisors) is None


def test_create_external_publisher_zmq(zmq_import, supvisors):
    """ Test the make_supvisors_rpcinterface function with zmq event link. """
    from supvisors.external_com.supvisorszmq import ZmqEventPublisher
    supvisors.options.event_link = EventLinks.ZMQ
    instance = create_external_publisher(supvisors)
    assert isinstance(instance, ZmqEventPublisher)


def test_create_external_publisher_ws_fail(ws_import, ws_fail_import, supvisors):
    """ Test the create_external_publisher function with websocket event link but not installed. """
    supvisors.options.event_link = EventLinks.WS
    assert create_external_publisher(supvisors) is None


def test_create_external_publisher_ws(ws_import, supvisors):
    """ Test the make_supvisors_rpcinterface function with websocket event link. """
    from supvisors.external_com.supvisorswebsocket import WsEventPublisher
    supvisors.options.event_link = EventLinks.WS
    instance = create_external_publisher(supvisors)
    try:
        assert isinstance(instance, WsEventPublisher)
    finally:
        time.sleep(0.5)
        instance.close()


def test_event_subscriber_interface():
    """ Test the EventSubscriberInterface class. """
    interface = EventSubscriberInterface()
    with pytest.raises(NotImplementedError):
        interface.on_supvisors_status('dummy body')
    with pytest.raises(NotImplementedError):
        interface.on_instance_status('dummy body')
    with pytest.raises(NotImplementedError):
        interface.on_application_status('dummy body')
    with pytest.raises(NotImplementedError):
        interface.on_process_event('dummy body')
    with pytest.raises(NotImplementedError):
        interface.on_process_status('dummy body')
    with pytest.raises(NotImplementedError):
        interface.on_host_statistics('dummy body')
    with pytest.raises(NotImplementedError):
        interface.on_process_statistics('dummy body')


def test_event_subscriber_creation(supvisors):
    """ Test the EventSubscriber constructor. """
    interface = EventSubscriberInterface()
    subscriber = EventSubscriber(interface, 'localhost', 7777, supvisors.logger)
    assert subscriber.intf is interface
    assert subscriber.node_name == 'localhost'
    assert subscriber.event_port == 7777
    assert subscriber.logger is supvisors.logger
    assert subscriber.headers == set()
    assert subscriber.thread is not None
    assert isinstance(subscriber.thread, AsyncEventThread)
    assert not subscriber.thread.is_alive()


@pytest.fixture
def interface():
    return Mock(spec=EventSubscriberInterface)


@pytest.fixture
def subscriber(supvisors, interface):
    return EventSubscriber(interface, 'localhost', 7777, supvisors.logger)


def test_event_subscriber_mainloop(subscriber):
    """ Test the EventSubscriber mainloop abstract method. """
    coro = subscriber.mainloop(asyncio.Event(), 'localhost', 7777)
    with pytest.raises(NotImplementedError):
        asyncio.get_event_loop().run_until_complete(coro)


async def mocked_loop(*args):
    counter = 5
    while counter > 0 and not args[0].is_set():
        await asyncio.sleep(0.5)
        counter -= 1


def test_event_subscriber_thread(mocker, subscriber):
    """ Test the EventSubscriber class. """
    # patch the mainloop to avoid that the thread exits immediately
    mocker.patch.object(subscriber, 'mainloop', side_effect=mocked_loop)
    # reset so that the coroutine is taken into account by the async thread
    subscriber.reset()
    # test that calling stop before start is not an issue
    subscriber.stop()
    assert not subscriber.thread.is_alive()
    # start the thread
    subscriber.start()
    time.sleep(1)
    assert subscriber.thread.is_alive()
    # stop the thread
    subscriber.stop()
    assert not subscriber.thread.is_alive()


def test_event_subscriber_on_receive_supvisors_status(interface, subscriber):
    """ Test the reception of a Supvisors status message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.SUPVISORS.value, 'supvisors status')
    assert interface.on_supvisors_status.call_args_list == [call('supvisors status')]
    assert not interface.on_instance_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_event.called
    assert not interface.on_process_status.called
    assert not interface.on_host_statistics.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_on_receive_instance_status(interface, subscriber):
    """ Test the reception of an Instance status message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.INSTANCE.value, 'instance status')
    assert interface.on_instance_status.call_args_list == [call('instance status')]
    assert not interface.on_supvisors_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_event.called
    assert not interface.on_process_status.called
    assert not interface.on_host_statistics.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_on_receive_application_status(interface, subscriber):
    """ Test the reception of an Application status message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.APPLICATION.value, 'application status')
    assert interface.on_application_status.call_args_list == [call('application status')]
    assert not interface.on_supvisors_status.called
    assert not interface.on_instance_status.called
    assert not interface.on_process_event.called
    assert not interface.on_process_status.called
    assert not interface.on_host_statistics.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_on_receive_process_event(interface, subscriber):
    """ Test the reception of a Supvisors status message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.PROCESS_EVENT.value, 'process event')
    assert interface.on_process_event.call_args_list == [call('process event')]
    assert not interface.on_supvisors_status.called
    assert not interface.on_instance_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_status.called
    assert not interface.on_host_statistics.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_on_receive_process_status(interface, subscriber):
    """ Test the reception of a Process status message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.PROCESS_STATUS.value, 'process status')
    assert interface.on_process_status.call_args_list == [call('process status')]
    assert not interface.on_supvisors_status.called
    assert not interface.on_instance_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_event.called
    assert not interface.on_host_statistics.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_on_receive_host_statistics(interface, subscriber):
    """ Test the reception of a Host Statistics message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.HOST_STATISTICS.value, 'host statistics')
    assert interface.on_host_statistics.call_args_list == [call('host statistics')]
    assert not interface.on_supvisors_status.called
    assert not interface.on_instance_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_event.called
    assert not interface.on_process_status.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_on_receive_process_statistics(interface, subscriber):
    """ Test the reception of a Process Statistics message in the EventSubscriber class. """
    subscriber.on_receive(EventHeaders.PROCESS_STATISTICS.value, 'process statistics')
    assert interface.on_process_statistics.call_args_list == [call('process statistics')]
    assert not interface.on_supvisors_status.called
    assert not interface.on_instance_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_event.called
    assert not interface.on_process_status.called
    assert not interface.on_host_statistics.called


def test_event_subscriber_on_receive_unknown(interface, subscriber):
    """ Test the reception of an unknown message in the EventSubscriber class. """
    with pytest.raises(ValueError):
        subscriber.on_receive('dummy header', 'dummy body')
    assert not interface.on_supvisors_status.called
    assert not interface.on_instance_status.called
    assert not interface.on_application_status.called
    assert not interface.on_process_event.called
    assert not interface.on_process_status.called
    assert not interface.on_host_statistics.called
    assert not interface.on_process_statistics.called


def test_event_subscriber_subscriptions(subscriber):
    """ Test the EventSubscriber subscription and unsubscription methods. """
    assert subscriber.headers == set()
    subscriber.subscribe_all()
    all_headers = {'application', 'hstats', 'instance', 'event', 'pstats', 'process', 'supvisors'}
    assert subscriber.headers == all_headers
    assert subscriber.all_subscriptions()
    # test that subscribe to anything already subscribed works and does not change anything
    for header in EventHeaders:
        subscriber.subscribe(header)
        assert subscriber.headers == all_headers
        assert subscriber.all_subscriptions()
    # unsubscribe one by one
    subscriber.unsubscribe_supvisors_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'application', 'hstats', 'instance', 'event', 'pstats', 'process'}
    subscriber.unsubscribe_instance_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'application', 'hstats', 'event', 'pstats', 'process'}
    subscriber.unsubscribe_application_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'hstats', 'event', 'pstats', 'process'}
    subscriber.unsubscribe_process_event()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'hstats', 'pstats', 'process'}
    subscriber.unsubscribe_process_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'hstats', 'pstats'}
    subscriber.unsubscribe_host_statistics()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'pstats'}
    subscriber.unsubscribe_process_statistics()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == set()
    # test that unsubscribe from anything already unsubscribed works and does not change anything
    for header in EventHeaders:
        subscriber.unsubscribe(header)
        assert subscriber.headers == set()
        assert not subscriber.all_subscriptions()
    # subscribe one by one
    subscriber.subscribe_process_statistics()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'pstats'}
    subscriber.subscribe_host_statistics()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'hstats', 'pstats'}
    subscriber.subscribe_process_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'hstats', 'pstats', 'process'}
    subscriber.subscribe_process_event()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'hstats', 'event', 'pstats', 'process'}
    subscriber.subscribe_application_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'application', 'hstats', 'event', 'pstats', 'process'}
    subscriber.subscribe_instance_status()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == {'application', 'hstats', 'instance', 'event', 'pstats', 'process'}
    subscriber.subscribe_supvisors_status()
    assert subscriber.all_subscriptions()
    assert subscriber.headers == all_headers
    # unsubscribe from all
    subscriber.unsubscribe_all()
    assert not subscriber.all_subscriptions()
    assert subscriber.headers == set()


@pytest.fixture
def event_thread():
    return AsyncEventThread(mocked_loop, 'localhost', 7777)


def test_async_event_thread_creation(event_thread):
    """ Test the EventSubscriber subscription and unsubscription methods. """
    assert event_thread.coro is mocked_loop
    assert event_thread.node_name == 'localhost'
    assert event_thread.event_port == 7777
    assert event_thread.loop is None
    assert event_thread.stop_event is None


def test_async_event_thread_run_stop(event_thread):
    """ Test the EventSubscriber class. """
    # test that calling stop before start is not an issue
    event_thread.stop()
    assert not event_thread.is_alive()
    # start the thread
    event_thread.start()
    time.sleep(1)
    assert event_thread.is_alive()
    # stop the thread
    event_thread.stop()
    event_thread.join()
    assert not event_thread.is_alive()
