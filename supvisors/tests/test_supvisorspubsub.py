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

from socket import gethostbyname, gethostname
from unittest.mock import MagicMock

import pytest

from supvisors.internal_com.pubsub import *

local_ip = gethostbyname(gethostname())


@pytest.fixture
def publisher(supvisors):
    local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
    emitter = InternalPublisher(local_instance.identifier,
                                local_instance.internal_port,
                                supvisors.logger)
    emitter.start()
    yield emitter
    emitter.close()


@pytest.fixture
def local_subscriber(supvisors, request):
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create subscriber
    subscriber = InternalAsyncSubscribers(queue, event, supvisors)
    subscriber.get_coroutines()  # not used, just hit it
    # local instance has been removed from the subscribers, but it's actually the only instance that can be tested here
    local_identifier = supvisors.supvisors_mapper.local_identifier
    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(subscriber.check_stop(), request.param),
                asyncio.wait_for(subscriber.create_coroutine(local_identifier), request.param)]
    return subscriber, all_coro


@pytest.mark.parametrize('local_subscriber', [6.0], indirect=True)
def test_global_normal(supvisors, publisher, local_subscriber):
    """ Test the Supvisors TCP publish / subscribe in one single test. """
    subscriber, all_coro = local_subscriber
    local_identifier = supvisors.supvisors_mapper.local_identifier

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # test publish TICK
        publisher.send_tick_event({'when': 1234})
        # test publish PROCESS
        publisher.send_process_state_event({'namespec': 'dummy_group:dummy_name', 'state': 'running'})
        # test publish PROCESS_ADDED
        publisher.send_process_added_event({'namespec': 'dummy_group:dummy_name'})
        # test publish PROCESS_REMOVED
        publisher.send_process_removed_event({'namespec': 'dummy_group:dummy_name'})
        # test publish PROCESS_DISABILITY
        publisher.send_process_disability_event({'name': 'dummy_name', 'disabled': True})
        # test publish HOST_STATISTICS
        publisher.send_host_statistics({'cpu': 25.3, 'mem': 12.5})
        # test publish PROCESS_STATISTICS
        publisher.send_process_statistics({'dummy_process': {'cpu': 25.3, 'mem': 12.5}})
        # test publish for STATE
        publisher.send_state_event({'state': 'operational', 'mode': 'starting'})
        # test disconnect subscriber
        await asyncio.sleep(1.0)
        subscriber.disconnect_subscribers([local_identifier])
        # sleep a bit before full close
        await asyncio.sleep(1.0)
        subscriber.global_stop_event.set()

    async def check_output():
        addr = local_ip, 65100
        queue = subscriber.queue
        # test subscribe TICK
        expected = InternalEventHeaders.TICK, {'when': 1234}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe PROCESS
        expected = InternalEventHeaders.PROCESS, {'namespec': 'dummy_group:dummy_name', 'state': 'running'}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe PROCESS_ADDED
        expected = InternalEventHeaders.PROCESS_ADDED, {'namespec': 'dummy_group:dummy_name'}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe PROCESS_REMOVED
        expected = InternalEventHeaders.PROCESS_REMOVED, {'namespec': 'dummy_group:dummy_name'}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe PROCESS_DISABILITY
        expected = InternalEventHeaders.PROCESS_DISABILITY, {'name': 'dummy_name', 'disabled': True}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe HOST_STATISTICS
        expected = InternalEventHeaders.HOST_STATISTICS, {'cpu': 25.3, 'mem': 12.5}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe PROCESS_STATISTICS
        expected = InternalEventHeaders.PROCESS_STATISTICS, {'dummy_process': {'cpu': 25.3, 'mem': 12.5}}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
        # test subscribe STATE
        expected = InternalEventHeaders.STATE, {'state': 'operational', 'mode': 'starting'}
        assert await asyncio.wait_for(queue.get(), 2.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])

    all_tasks = asyncio.gather(publisher_task(), check_output(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


# testing exception cases (by line number)
def test_publisher_bind_exception(supvisors):
    """ Test the bind exception of the PublisherServer.
    The aim is to hit the lines 114-116 in PublisherServer._bind.
    Checked ok with debugger.
    """
    local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
    # start a first publisher server
    server1 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    assert server1.server is not None
    # wait for publisher server to be alive
    server1.start()
    time.sleep(1)
    assert server1.is_alive()
    # start a second publisher server on the same port
    server2 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    assert server2.server is None
    # the publisher server thread will stop immediately
    server2.start()
    time.sleep(1)
    assert not server2.is_alive()
    # close all
    server1.stop()
    server2.stop()


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_publisher_accept_exception(mocker, supvisors, publisher, local_subscriber):
    """ Test the accept exception of the PublisherServer.
    The aim is to hit the line 212-214 in PublisherServer._handle_events.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber
    # socket.accept is read-only and cannot be mocked, so mock _add_client
    mocker.patch.object(publisher, '_add_client', side_effect=OSError)

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # no subscriber could connect the local publisher instance
        assert len(publisher.clients) == 0
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_publisher_forward_empty_message(supvisors, publisher, local_subscriber):
    """ Test the robustness when the publisher forwards an empty message.
    The aim is to hit the lines 233-234 in PublisherServer._forward_message.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # send a 0-sized message to the subscriber interface
        buffer = int.to_bytes(0, 4, 'big')
        publisher.put_sock.sendall(buffer)
        # wait for publisher server to die
        await asyncio.sleep(1.0)
        assert not publisher.is_alive()
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_publisher_receive_empty_message(mocker, publisher, local_subscriber):
    """ Test the robustness when the publisher receives an empty message.
    The aim is to hit the lines 249-250 in PublisherServer._receive_client_heartbeat.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    # mock the send_heartbeat coroutine so that it sends 0-sized heartbeat messages
    class SendHeartbeat(MagicMock):
        async def __call__(self, writer: asyncio.StreamWriter):
            writer.write(int.to_bytes(0, 4, 'big'))
            await writer.drain()
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.send_heartbeat', new_callable=SendHeartbeat)

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # reconnection will not have time to happen
        await asyncio.sleep(1.0)
        assert publisher.clients == {}
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [15.0], indirect=True)
def test_publisher_heartbeat_timeout(mocker, publisher, local_subscriber):
    """ Test the exception management in PublisherServer when heartbeat missing from a client.
    The aim is to hit the lines 278-280 in PublisherServer._manage_heartbeats.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    # mock the send_heartbeat coroutine so that it doesn't send heartbeat messages
    class SendHeartbeat(MagicMock):
        async def __call__(self, writer: asyncio.StreamWriter):
            pass
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.send_heartbeat', new_callable=SendHeartbeat)

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # let missing heartbeat have its consequences
        await asyncio.sleep(10.0)
        assert publisher.clients == {}
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_publisher_publish_message_exception(publisher, local_subscriber):
    """ Test the publish exception management in PublisherServer when the client is closed.
    The aim is to hit the line 294-296 in PublisherServer._publish_message.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # close the client and send a message
        client = next(x for x in publisher.clients.values())
        client.socket.shutdown(SHUT_RDWR)
        # publish a message
        publisher._publish_message(b'hello')
        # check that the client is removed
        assert publisher.clients == {}
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_publisher_emit_message_exception(publisher):
    """ Test the sendall exception of the InternalPublisher.
    The aim is to hit the lines 324-327 in InternalPublisher.emit_message.
    Checked ok with debugger.
    """
    # wait for publisher server to be alive
    time.sleep(1)
    assert publisher.is_alive()
    # close the internal put socket
    publisher.put_sock.close()
    # try to publish a message
    publisher.emit_message(InternalEventHeaders.TICK, {})
    # wait for publisher server to be alive
    time.sleep(1)
    assert not publisher.is_alive()


@pytest.mark.parametrize('local_subscriber', [8.0], indirect=True)
def test_subscriber_read_error(publisher, local_subscriber):
    """ Test the exception management in subscriber when a message cannot be read completely.
    The aim is to hit the lines 395-397 in InternalAsyncSubscriber.handle_subscriber.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # publish an incomplete message
        client = next(x for x in publisher.clients.values())
        client.socket.sendall(int.to_bytes(6, 4, 'big') + b'hello')
        # sleep a bit so that reconnection takes place
        await asyncio.sleep(4.0)
        assert len(publisher.clients) == 1
        new_client = next(x for x in publisher.clients.values())
        assert new_client is not client
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [20.0], indirect=True)
def test_subscriber_recv_heartbeat_exception(mocker, publisher, local_subscriber):
    """ Test the exception management when sending heartbeat to a socket that has been closed.
    The aim is to hit the lines 420-422 in InternalSubscriber.handle_subscriber.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    # mock publisher so that it does not publish heartbeat messages
    mocker.patch.object(publisher, '_manage_heartbeats')

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        ref_client = next(x for x in publisher.clients.values())
        # NOTE: it takes 10 seconds for the subscriber to detect the failure and reconnect
        #       and a few seconds for the publisher to detect the subscriber absence
        #       then a new subscriber connects
        await asyncio.sleep(15.0)
        assert len(publisher.clients) == 1
        new_client = next(x for x in publisher.clients.values())
        assert new_client is not ref_client
        # full close
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_subscriber_connection_refused(publisher, local_subscriber):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 431-432 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber
    publisher.close()

    async def stop_task():
        await asyncio.sleep(1.0)
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(stop_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_subscriber_connection_timeout(mocker, publisher, local_subscriber):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 433-434 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber
    # set the ASYNC_TIMEOUT to 0, so that the connection times out
    mocker.patch('supvisors.internal_com.pubsub.ASYNC_TIMEOUT', 0)

    async def stop_task():
        await asyncio.sleep(1.0)
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(stop_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


@pytest.mark.parametrize('local_subscriber', [4.0], indirect=True)
def test_subscriber_connection_reset(mocker, publisher, local_subscriber):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 435-436 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    subscriber, all_coro = local_subscriber

    # this one is tricky to raise from within handle_subscriber
    # can't do better than simply mock handle_subscriber
    class HandleSubscriber(MagicMock):
        async def __call__(self):
            raise ConnectionResetError
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.handle_subscriber',
                 new_callable=HandleSubscriber)

    async def stop_task():
        await asyncio.sleep(1.0)
        subscriber.global_stop_event.set()

    all_tasks = asyncio.gather(stop_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)
