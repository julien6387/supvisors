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
def subscriber(supvisors, request):
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create subscriber
    test_subscriber = InternalAsyncSubscribers(queue, event, supvisors)
    # WARN: local instance has been removed from the subscribers, but it's actually the only instance
    #       that can be tested here
    #       so add a Supvisors instance that has the same parameters as the local Supvisors instance,
    #       but with a different name
    local_instance_id: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
    supvisors.supvisors_mapper.instances['async_test'] = local_instance_id
    return test_subscriber


def test_global_normal(supvisors, publisher, subscriber):
    """ Test the Supvisors TCP publish / subscribe in one single test. """
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

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 8.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), check_output(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


# testing exception cases (by line number)
def test_publisher_heartbeat_timeout(mocker, publisher, subscriber):
    """ Test the exception management in PublisherServer when heartbeat missing from a client.
    The aim is to hit the lines:
        * 88-90 in SubscriberClient.manage_heartbeat ;
        * 205 in PublisherServer.handle_supvisors_client.
    Checked ok with debugger.
    """
    # mock the send_heartbeat coroutine so that it doesn't send heartbeat messages
    class SendHeartbeat(MagicMock):
        async def __call__(self, writer: asyncio.StreamWriter):
            pass
    mocker.patch('supvisors.internal_com.pubsub.InternalAsyncSubscriber.send_heartbeat', new_callable=SendHeartbeat)

    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(2.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # let missing heartbeat have its consequences
        await asyncio.sleep(10.0)
        assert publisher.clients == []
        # full close
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 15.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_publisher_forward_empty_message(supvisors, publisher, subscriber):
    """ Test the robustness when the publisher forwards an empty message.
    The aim is to hit the lines 166-167 in PublisherServer.handle_publications.
    Checked ok with debugger.
    """
    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(2.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
        # send a 0-sized message to the subscriber interface
        buffer = int.to_bytes(0, 4, 'big')
        publisher.put_sock.sendall(buffer)
        # wait for publisher server to die
        await asyncio.sleep(2.0)
        assert not publisher.is_alive()
        # full close
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 8.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)
    print('All tasks completed')


def test_publisher_publish_message_exception(mocker, publisher, subscriber):
    """ Test the publish exception management in PublisherServer when the client is closed.
    The aim is to hit the line 175-177 in PublisherServer.handle_publications.
    Checked ok with debugger.
    """
    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
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
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 5.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_publisher_receive_empty_message(mocker, publisher, subscriber):
    """ Test the robustness when the publisher receives an empty message from a subscriber.
    The aim is to hit the lines 193-195 in PublisherServer.handle_supvisors_client.
    Checked ok with debugger.
    """
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
        assert publisher.clients == []
        # full close
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 5.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_publisher_bind_exception(supvisors):
    """ Test the bind exception of the PublisherServer.
    The aim is to hit the lines 219-224 in PublisherServer.open_supvisors_server.
    Checked ok with debugger.
    """
    local_instance: SupvisorsInstanceId = supvisors.supvisors_mapper.local_instance
    # start a first publisher server
    server1 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    # wait for publisher server to be alive
    server1.start()
    time.sleep(1)
    assert server1.is_alive()
    # the publisher server is set
    assert server1.server is not None
    # start a second publisher server on the same port
    server2 = PublisherServer(local_instance.identifier, local_instance.internal_port, supvisors.logger)
    # the publisher server thread will stop immediately
    server2.start()
    time.sleep(1)
    assert server2.is_alive()
    # the publisher server is not set
    assert server2.server is None
    # close all
    server1.stop()
    server2.stop()


def test_publisher_emit_message_exception(publisher):
    """ Test the sendall exception of the InternalPublisher.
    The aim is to hit the lines 270-273 in InternalPublisher.emit_message.
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


def test_subscriber_read_error(publisher, subscriber):
    """ Test the exception management in subscriber when a message cannot be read completely.
    The aim is to hit the lines 340-342 in InternalAsyncSubscriber.handle_subscriber.
    Checked ok with debugger.
    """
    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(1.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
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
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 8.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_subscriber_recv_heartbeat_exception(publisher, subscriber):
    """ Test the exception management when sending heartbeat to a socket that has been closed.
    The aim is to hit the lines 367-369 in InternalSubscriber.handle_subscriber.
    Checked ok with debugger.
    """
    async def publisher_task():
        # wait for publisher server to be alive
        await asyncio.sleep(2.0)
        assert publisher.is_alive()
        # the local subscriber has connected the local publisher instance
        assert len(publisher.clients) == 1
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
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 20.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(publisher_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_subscriber_connection_timeout(mocker, publisher, subscriber):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 378-379 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    # set the ASYNC_TIMEOUT to 0, so that the connection times out
    mocker.patch('supvisors.internal_com.pubsub.ASYNC_TIMEOUT', 0)

    async def stop_task():
        await asyncio.sleep(1.0)
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 5.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(stop_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_subscriber_connection_reset(mocker, publisher, subscriber):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 380-381 in InternalSubscriber.auto_connect.
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
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 5.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(stop_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)


def test_subscriber_connection_refused(publisher, subscriber):
    """ Test the exception management when connecting the publisher.
    The aim is to hit the lines 382-384 in InternalSubscriber.auto_connect.
    Checked ok with debugger.
    """
    publisher.close()

    async def stop_task():
        await asyncio.sleep(1.0)
        subscriber.global_stop_event.set()

    # auto_connect and check_stop can loop forever, so add a wait_for just in case something goes wrong
    all_coro = [asyncio.wait_for(coro, 5.0) for coro in subscriber.get_coroutines()]
    all_tasks = asyncio.gather(stop_task(), *all_coro)
    asyncio.get_event_loop().run_until_complete(all_tasks)
