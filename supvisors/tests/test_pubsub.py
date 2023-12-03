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
def stop_event():
    return asyncio.Event()


@pytest.fixture
def publisher(supvisors):
    """ Create the InternalPublisher instance to test. """
    local_instance: SupvisorsInstanceId = supvisors.mapper.local_instance
    emitter = InternalPublisher(local_instance.identifier,
                                local_instance.internal_port,
                                supvisors.logger)
    emitter.start()
    yield emitter
    emitter.close()


@pytest.fixture
def subscriber(stop_event, supvisors):
    """ Create the InternalPublisher instance to test. """
    queue = asyncio.Queue()
    test_subscriber = InternalAsyncSubscribers(queue, stop_event, supvisors)
    # WARN: local instance has been removed from the subscribers, but it's actually the only instance
    #       that can be tested here
    #       so add a Supvisors instance that has the same parameters as the local Supvisors instance,
    #       but with a different name
    mapper = supvisors.mapper
    local_instance_id: SupvisorsInstanceId = mapper.local_instance
    mapper._instances = {'async_test': local_instance_id,
                         mapper.local_identifier: local_instance_id}
    return test_subscriber


async def wait_alive_and_connected(publisher, max_time: int = 10) -> bool:
    """ Wait for publisher to be alive and connected to one client. """
    nb_tries = max_time
    while nb_tries > 0 and not (publisher.loop and publisher.loop.is_running() and len(publisher.clients) == 1):
        await asyncio.sleep(1.0)
        nb_tries -= 1
    return publisher.loop and publisher.loop.is_running() and len(publisher.clients) == 1


async def wait_closed(publisher, max_time: int = 2) -> bool:
    """ Wait for publisher to be closed. """
    nb_tries = max_time
    while nb_tries > 0 and publisher.loop:
        await asyncio.sleep(1.0)
        nb_tries -= 1
    return publisher.loop is None


async def run_async_tasks(subscriber, coroutines, timeout: float):
    """ Run the asynchronous tasks in concurrence with the subscriber tasks. """
    # some subscriber tasks can loop forever, so add a wait_for just in case something goes wrong
    subscriber_coro = [asyncio.wait_for(coro, timeout)
                       for coro in subscriber.get_coroutines()]
    await asyncio.gather(*coroutines, *subscriber_coro)


@pytest.mark.asyncio
async def test_global_normal(supvisors, publisher, subscriber, stop_event):
    """ Test the Supvisors TCP publish / subscribe in one single test. """
    local_identifier = supvisors.mapper.local_identifier

    async def publisher_task():
        # wait for publisher server to be alive
        assert await wait_alive_and_connected(publisher)
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
        stop_event.set()

    async def check_output():
        addr = local_ip, 65100
        queue = subscriber.queue
        # test subscribe TICK
        expected = InternalEventHeaders.TICK, {'when': 1234}
        assert await asyncio.wait_for(queue.get(), 6.0) == (addr, [expected[0].value, [local_identifier, expected[1]]])
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

    await run_async_tasks(subscriber, [publisher_task(), check_output()], 14.0)


# testing exception cases (by line number)
@pytest.mark.asyncio
async def test_publisher_write_stream_exception(mocker, publisher, subscriber, stop_event):
    """ Test the write_stream failure when the subscriber is closed.
    The aim is to hit the line 84 in SubscriberClient.manage_heartbeat.
    Checked ok with debugger.
    """
    # mock the send_heartbeat coroutine so that it doesn't send heartbeat messages
    class WriteStream(MagicMock):
        async def __call__(self, writer: asyncio.StreamWriter, message: bytes):
            return False
    mocker.patch('supvisors.internal_com.pubsub.write_stream', new_callable=WriteStream)

    async def publisher_task():
        assert await wait_alive_and_connected(publisher)
        ref_client = publisher.clients[0]
        # due to
        await asyncio.sleep(1.0)
        assert publisher.clients == [] or publisher.clients[0] is not ref_client
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 13.0)


@pytest.mark.asyncio
async def test_publisher_heartbeat_timeout(mocker, publisher, subscriber, stop_event):
    """ Test the exception management in PublisherServer when heartbeat missing from a client.
    The aim is to hit the lines:
        * 88-90 in SubscriberClient.manage_heartbeat ;
        * 204 in PublisherServer.handle_supvisors_client.
    Checked ok with debugger.
    """
    # mock the send_heartbeat coroutine so that it doesn't send heartbeat messages
    class SendHeartbeat(MagicMock):
        async def __call__(self, writer: asyncio.StreamWriter):
            pass
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.send_heartbeat', new_callable=SendHeartbeat)

    async def publisher_task():
        assert await wait_alive_and_connected(publisher)
        # let missing heartbeat have its consequences
        await asyncio.sleep(10.0)
        assert publisher.clients == []
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 22.0)


@pytest.mark.asyncio
async def test_publisher_forward_empty_message(publisher, subscriber, stop_event):
    """ Test the robustness when the publisher forwards an empty message.
    The aim is to hit the lines 167-168 in PublisherServer.handle_publications.
    Checked ok with debugger.
    """
    async def publisher_task():
        # wait for publisher server to be alive
        assert await wait_alive_and_connected(publisher)
        # send a 0-sized message to the subscriber interface
        buffer = int.to_bytes(0, 4, 'big')
        publisher.put_sock.sendall(buffer)
        # wait for publisher server to die
        assert await wait_closed(publisher)
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 14.0)


@pytest.mark.asyncio
async def test_publisher_publish_message_exception(mocker, publisher, subscriber, stop_event):
    """ Test the publish exception management in PublisherServer when the client is closed.
    The aim is to hit the line 174-176 in PublisherServer.handle_publications.
    Checked ok with debugger.
    """
    async def publisher_task():
        assert await wait_alive_and_connected(publisher)
        # close the client and send a message
        client = publisher.clients[0]
        client.last_sent_heartbeat_time = time.time() + 10
        mocker.patch.object(client.writer, 'write', side_effect=OSError)
        # publish a message
        publisher.send_tick_event({'when': 1234})
        # check that the client is removed
        await asyncio.sleep(1.0)
        assert publisher.clients == []
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 11.0)


@pytest.mark.asyncio
async def test_publisher_receive_empty_message(mocker, publisher, subscriber, stop_event):
    """ Test the robustness when the publisher receives an empty message from a subscriber.
    The aim is to hit the lines 192-194 in PublisherServer.handle_supvisors_client.
    Checked ok with debugger.
    """
    # mock the send_heartbeat coroutine so that it sends 0-sized heartbeat messages
    class SendHeartbeat(MagicMock):
        async def __call__(self, writer: asyncio.StreamWriter):
            writer.write(int.to_bytes(0, 4, 'big'))
            await writer.drain()
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.send_heartbeat', new_callable=SendHeartbeat)

    async def publisher_task():
        assert await wait_alive_and_connected(publisher)
        # reconnection will not have time to happen
        await asyncio.sleep(1.0)
        assert publisher.clients == []
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 13.0)


def test_publisher_bind_exception(supvisors):
    """ Test the bind exception of the PublisherServer.
    The aim is to hit the lines 220-226 in PublisherServer.open_supvisors_server.
    Checked ok with debugger.
    """
    local_instance: SupvisorsInstanceId = supvisors.mapper.local_instance
    # create 2 publisher servers
    server1 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    server2 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    try:
        # wait for the first publisher server to be alive
        server1.start()
        time.sleep(1)
        assert server1.is_alive()
        # the publisher server is set
        assert server1.server is not None
        # wait for the second publisher server to be alive
        server2.start()
        time.sleep(1)
        assert server2.is_alive()
        # the publisher server is not set (bind failed)
        assert server2.server is None
    finally:
        # close all servers properly even if an assertion was raised
        server1.stop()
        server2.stop()


def test_publisher_emit_message_exception(publisher):
    """ Test the sendall exception of the InternalPublisher.
    The aim is to hit the lines 274-277 in InternalPublisher.emit_message.
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


@pytest.mark.asyncio
async def test_subscriber_read_error(publisher, subscriber, stop_event):
    """ Test the exception management in subscriber when a message cannot be read completely.
    The aim is to hit the lines 344-346 in InternalAsyncSubscriber.handle_subscriber.
    Checked ok with debugger.
    """
    async def publisher_task():
        assert await wait_alive_and_connected(publisher)
        # publish an incomplete message (make sure that heartbeat will not interfere)
        client = publisher.clients[0]
        client.last_sent_heartbeat_time = time.time() + 5
        client.writer.write(int.to_bytes(6, 4, 'big'))
        client.writer.write(b'hello')
        await client.writer.drain()
        # sleep a bit so that reconnection takes place
        await asyncio.sleep(4.0)
        assert len(publisher.clients) == 1
        new_client = publisher.clients[0]
        assert new_client is not client
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 16.0)


@pytest.mark.asyncio
async def test_subscriber_recv_heartbeat_exception(publisher, subscriber, stop_event):
    """ Test the exception management when sending heartbeat to a socket that has been closed.
    The aim is to hit the lines 371-373 in InternalSubscriber.handle_subscriber.
    Checked ok with debugger.
    """
    async def publisher_task():
        assert await wait_alive_and_connected(publisher)
        ref_client = publisher.clients[0]
        # ensure publisher client will not publish heartbeat messages
        ref_client.last_sent_heartbeat_time = time.time() + 20
        # NOTE: it takes 10 seconds for the subscriber to detect the failure and reconnect
        #       and a few seconds for the publisher to detect the subscriber absence
        #       then a new subscriber connects
        await asyncio.sleep(15.0)
        assert len(publisher.clients) == 1
        new_client = publisher.clients[0]
        assert new_client is not ref_client
        # full close
        stop_event.set()

    await run_async_tasks(subscriber, [publisher_task()], 27.0)


@pytest.mark.asyncio
async def test_subscriber_connection_timeout(mocker, publisher, subscriber, stop_event):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 382-383 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    # set the ASYNC_TIMEOUT to 0, so that the connection times out
    mocker.patch('supvisors.internal_com.pubsub.ASYNC_TIMEOUT', 0)

    async def stop_task():
        await asyncio.sleep(1.0)
        stop_event.set()

    await run_async_tasks(subscriber, [stop_task()], 5.0)


@pytest.mark.asyncio
async def test_subscriber_connection_reset(mocker, publisher, subscriber, stop_event):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 384-385 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    # this one is tricky to raise from within handle_subscriber
    # can't do better than simply mock handle_subscriber
    class HandleSubscriber(MagicMock):
        async def __call__(self):
            raise ConnectionResetError
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.handle_subscriber',
                 new_callable=HandleSubscriber)

    async def stop_task():
        await asyncio.sleep(1.0)
        stop_event.set()

    await run_async_tasks(subscriber, [stop_task()], 5.0)


@pytest.mark.asyncio
async def test_subscriber_connection_refused(publisher, subscriber, stop_event):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 386-388 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    publisher.close()

    async def stop_task():
        await asyncio.sleep(1.0)
        stop_event.set()

    await run_async_tasks(subscriber, [stop_task()], 5.0)
