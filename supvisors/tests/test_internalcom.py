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

from socket import socket
from threading import Timer

import pytest

from supvisors.internal_com.internal_com import *


@pytest.fixture
def emitter(supvisors, request) -> SupvisorsInternalEmitter:
    """ Fixture for the instance to test. """
    if request.param == 'discovery':
        supvisors.options.multicast_group = '239.0.0.1', 7777
    emitter_test = SupvisorsInternalEmitter(supvisors)
    yield emitter_test
    emitter_test.stop()


@pytest.mark.parametrize('emitter', [''], indirect=True)
def test_emitter(supvisors, emitter):
    """ Test the SupvisorsInternalEmitter with no discovery mode. """
    assert emitter.supvisors is supvisors
    ref_pusher = emitter.pusher_sock
    ref_puller = emitter.puller_sock
    ref_request = emitter.pusher
    assert type(ref_pusher) is socket
    assert type(ref_puller) is socket
    assert type(ref_request) is RpcPusher
    assert emitter.pusher.socket is emitter.pusher_sock
    assert emitter.mc_sender is None


@pytest.mark.parametrize('emitter', ['discovery'], indirect=True)
def test_emitter_discovery(supvisors, emitter):
    """ Test the SupvisorsInternalEmitter with discovery mode. """
    ref_mc_sender = emitter.mc_sender
    assert emitter.supvisors is supvisors
    assert type(emitter.pusher_sock) is socket
    assert type(emitter.puller_sock) is socket
    assert type(emitter.pusher) is RpcPusher
    assert emitter.pusher.socket is emitter.pusher_sock
    assert type(ref_mc_sender) is MulticastSender
    # test close
    emitter.stop()


@pytest.fixture
def receiver(supvisors, request) -> SupvisorsInternalReceiver:
    """ Fixture for the instance to test. """
    if request.param == 'discovery':
        supvisors.options.multicast_group = '239.0.0.1', 7777
    # store a real unix socket in emitter
    supvisors.internal_com.puller_sock, _ = socketpair()
    loop = asyncio.get_event_loop()
    internal_receiver = SupvisorsInternalReceiver(loop, supvisors)
    return internal_receiver


@pytest.mark.asyncio
@pytest.mark.parametrize('receiver', [''], indirect=True)
async def test_receiver(supvisors, receiver):
    """ Test the SupvisorsInternalReceiver with no discovery mode. """
    assert receiver.supvisors is supvisors
    assert receiver.loop is asyncio.get_event_loop()
    assert not receiver.stop_event.is_set()
    assert receiver.requester_queue.empty()
    assert receiver.discovery_queue.empty()
    assert type(receiver.puller) is AsyncRpcPuller
    assert receiver.discovery_coro is None
    # test the number of tasks (only puller)
    tasks = receiver.get_tasks()
    try:
        assert all(asyncio.iscoroutine(x) for x in tasks)
        assert len(tasks) == 1
    finally:
        # avoid warnings about coroutines never awaited
        receiver.stop_event.set()
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
@pytest.mark.parametrize('receiver', ['discovery'], indirect=True)
async def test_receiver_discovery(supvisors, receiver):
    """ Test the SupvisorsInternalReceiver with discovery mode. """
    assert receiver.supvisors is supvisors
    assert receiver.loop is asyncio.get_event_loop()
    assert not receiver.stop_event.is_set()
    assert receiver.requester_queue.empty()
    assert receiver.discovery_queue.empty()
    assert type(receiver.puller) is AsyncRpcPuller
    assert asyncio.iscoroutine(receiver.discovery_coro)
    # test the number of tasks (puller + discovery)
    tasks = receiver.get_tasks()
    try:
        assert all(asyncio.iscoroutine(x) for x in tasks)
        assert len(tasks) == 2
    finally:
        # avoid warnings about coroutines never awaited
        receiver.stop_event.set()
        await asyncio.gather(*tasks)


@pytest.mark.asyncio
@pytest.mark.parametrize('receiver', [''], indirect=True)
async def test_receiver_stop(supvisors, receiver):
    """ Test the SupvisorsInternalReceiver stop method. """
    # trigger the SupvisorsInternalReceiver stop in one second
    Timer(1.0, receiver.stop).start()
    # stop_event can hang on forever, so add a wait_for just in case something goes wrong
    await asyncio.wait_for(receiver.stop_event.wait(), 5.0)
    assert receiver.stop_event.is_set()
