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

from socket import socketpair

import pytest

from supvisors.internal_com.pushpull import *


def test_deferred_request_headers():
    """ Test the DeferredRequestHeaders enumeration. """
    expected = ['CHECK_INSTANCE', 'ISOLATE_INSTANCES', 'CONNECT_INSTANCE', 'START_PROCESS', 'STOP_PROCESS',
                'RESTART', 'SHUTDOWN', 'RESTART_SEQUENCE', 'RESTART_ALL', 'SHUTDOWN_ALL']
    assert [x.name for x in DeferredRequestHeaders] == expected


@pytest.fixture
def push_pull():
    """ Return a pair of sockets to be used for Push / Pull. """
    return socketpair()


@pytest.mark.asyncio
async def test_push_pull_end_event(supvisors, push_pull):
    """ Test the Push / Pull communication.
    Termination on event. """
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create puller
    supvisors.internal_com.puller_sock = push_pull[1]
    puller = RequestAsyncPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        pusher = RequestPusher(push_pull[0], supvisors.logger)
        assert pusher.logger is supvisors.logger
        # test push CHECK_INSTANCE
        pusher.send_check_instance('10.0.0.1')
        # test push ISOLATE_INSTANCES
        pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
        # test push ISOLATE_INSTANCES
        pusher.send_connect_instance('10.0.0.1')
        # test push START_PROCESS
        pusher.send_start_process('10.0.0.1', 'group:name', 'extra args')
        # test push STOP_PROCESS
        pusher.send_stop_process('10.0.0.1', 'group:name')
        # test push RESTART
        pusher.send_restart('10.0.0.1')
        # test push SHUTDOWN
        pusher.send_shutdown('10.0.0.1')
        # test push RESTART_SEQUENCE
        pusher.send_restart_sequence('10.0.0.1')
        # test push RESTART_ALL
        pusher.send_restart_all('10.0.0.1')
        # test push SHUTDOWN_ALL
        pusher.send_shutdown_all('10.0.0.1')
        # test timeout on reception
        await asyncio.sleep(1.5)
        event.set()

    async def check_output():
        """ test of the puller output """
        # test subscribe CHECK_INSTANCE
        expected = [DeferredRequestHeaders.CHECK_INSTANCE.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe ISOLATE_INSTANCES
        expected = [DeferredRequestHeaders.ISOLATE_INSTANCES.value, ['10.0.0.1', '10.0.0.2']]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe CONNECT_INSTANCE
        expected = [DeferredRequestHeaders.CONNECT_INSTANCE.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe START_PROCESS
        expected = [DeferredRequestHeaders.START_PROCESS.value, ['10.0.0.1', 'group:name', 'extra args']]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe STOP_PROCESS
        expected = [DeferredRequestHeaders.STOP_PROCESS.value, ['10.0.0.1', 'group:name']]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe RESTART
        expected = [DeferredRequestHeaders.RESTART.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe SHUTDOWN
        expected = [DeferredRequestHeaders.SHUTDOWN.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe RESTART_SEQUENCE
        expected = [DeferredRequestHeaders.RESTART_SEQUENCE.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe RESTART_ALL
        expected = [DeferredRequestHeaders.RESTART_ALL.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test subscribe SHUTDOWN_ALL
        expected = [DeferredRequestHeaders.SHUTDOWN_ALL.value, ['10.0.0.1', ]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    await asyncio.gather(pusher_task(),
                         asyncio.wait_for(puller.handle_puller(), 5.0),
                         check_output())


@pytest.mark.asyncio
async def test_push_pull_end_eof(supvisors, push_pull):
    """ Test the Push / Pull communication.
    Termination on EOF. """
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create puller
    supvisors.internal_com.puller_sock = push_pull[1]
    puller = RequestAsyncPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        pusher = RequestPusher(push_pull[0], supvisors.logger)
        assert pusher.logger is supvisors.logger
        # test push CHECK_INSTANCE
        pusher.send_check_instance('10.0.0.1')
        push_pull[0].close()

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    await asyncio.gather(pusher_task(),
                         asyncio.wait_for(puller.handle_puller(), 2.0))


@pytest.mark.asyncio
async def test_push_pull_end_error(supvisors, push_pull):
    """ Test the Push / Pull communication.
    Termination on reading error. """
    queue = asyncio.Queue()
    event = asyncio.Event()
    # create puller
    supvisors.internal_com.puller_sock = push_pull[1]
    puller = RequestAsyncPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        # send incomplete header
        push_pull[0].sendall(int.to_bytes(4, 4, byteorder='big'))
        push_pull[0].sendall(b'foo')

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    await asyncio.gather(pusher_task(),
                         asyncio.wait_for(puller.handle_puller(), 5.0))


def test_push_error(supvisors, push_pull):
    """ Test the RequestPusher / push_message exception management.
    The aim is to hit the lines 197-198.
    Check OK with debugger. """
    pusher = RequestPusher(push_pull[0], supvisors.logger)
    push_pull[0].close()
    pusher.send_shutdown('10.0.0.1')
