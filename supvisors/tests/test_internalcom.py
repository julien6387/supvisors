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

from socket import socket
from threading import Timer

import pytest

from supvisors.internal_com.internal_com import *
from .conftest import wait_internal_publisher


@pytest.fixture
def emitter(supvisors, request) -> SupvisorsInternalEmitter:
    """ Fixture for the instance to test. """
    if request.param == 'discovery':
        supvisors.options.multicast_group = '239.0.0.1', 7777
    emitter_test = SupvisorsInternalEmitter(supvisors)
    # wait for the publisher to be alive to avoid stop issues
    assert wait_internal_publisher(emitter_test.publisher)
    yield emitter_test
    emitter_test.stop()


@pytest.mark.parametrize('emitter', [''], indirect=True)
def test_emitter(supvisors, emitter):
    """ Test the SupvisorsInternalEmitter with no discovery mode. """
    assert emitter.supvisors is supvisors
    ref_pusher = emitter.pusher_sock
    ref_puller = emitter.puller_sock
    ref_request = emitter.pusher
    ref_publisher = emitter.publisher
    assert type(ref_pusher) is socket
    assert type(ref_puller) is socket
    assert type(ref_request) is RequestPusher
    assert emitter.pusher.socket is emitter.pusher_sock
    assert type(ref_publisher) is InternalPublisher
    assert emitter.mc_sender is None
    assert emitter.intf_names == []
    # add interfaces and test no change for the first call
    emitter.check_intf(['lo'])
    assert emitter.intf_names == ['lo']
    assert ref_pusher is emitter.pusher_sock
    assert ref_puller is emitter.puller_sock
    assert ref_request is emitter.pusher
    assert ref_publisher is emitter.publisher
    # add interfaces again and check publisher restart
    emitter.check_intf(['lo', 'eth0'])
    assert wait_internal_publisher(emitter.publisher)
    assert emitter.intf_names == ['lo', 'eth0']
    assert ref_pusher is emitter.pusher_sock
    assert ref_puller is emitter.puller_sock
    assert ref_request is emitter.pusher
    assert ref_publisher is not emitter.publisher
    ref_publisher = emitter.publisher
    # remove interfaces and test no change on structures
    emitter.check_intf(['lo'])
    assert emitter.intf_names == ['lo']
    assert ref_pusher is emitter.pusher_sock
    assert ref_puller is emitter.puller_sock
    assert ref_request is emitter.pusher
    assert ref_publisher is emitter.publisher


@pytest.mark.parametrize('emitter', ['discovery'], indirect=True)
def test_emitter_discovery(supvisors, emitter):
    """ Test the SupvisorsInternalEmitter with discovery mode. """
    ref_mc_sender = emitter.mc_sender
    assert emitter.supvisors is supvisors
    assert type(emitter.pusher_sock) is socket
    assert type(emitter.puller_sock) is socket
    assert type(emitter.pusher) is RequestPusher
    assert emitter.pusher.socket is emitter.pusher_sock
    assert type(emitter.publisher) is InternalPublisher
    assert type(ref_mc_sender) is MulticastSender
    assert emitter.intf_names == []
    # quick test on interfaces with just the mc_sender
    # add interfaces and test no change for the first call
    emitter.check_intf(['lo'])
    assert emitter.intf_names == ['lo']
    assert ref_mc_sender is emitter.mc_sender
    # add interfaces again and check no change on MulticastSender
    emitter.check_intf(['lo', 'eth0'])
    assert wait_internal_publisher(emitter.publisher)
    assert emitter.intf_names == ['lo', 'eth0']
    assert ref_mc_sender is emitter.mc_sender
    # remove interfaces and test no change on structures
    emitter.check_intf(['eth0'])
    assert emitter.intf_names == ['eth0']
    assert ref_mc_sender is emitter.mc_sender
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
    assert receiver.subscriber_queue.empty()
    assert receiver.discovery_queue.empty()
    assert type(receiver.puller) is RequestAsyncPuller
    assert type(receiver.subscribers) is InternalAsyncSubscribers
    assert receiver.discovery_coro is None
    # test the number of tasks (one per Supvisors instance, local instance excepted, + stop, + puller)
    assert len(supvisors.mapper.instances) == 7
    tasks = receiver.get_tasks()
    try:
        assert all(asyncio.iscoroutine(x) for x in tasks)
        assert len(tasks) == len(supvisors.mapper.instances) + 1
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
    assert receiver.subscriber_queue.empty()
    assert receiver.discovery_queue.empty()
    assert type(receiver.puller) is RequestAsyncPuller
    assert type(receiver.subscribers) is InternalAsyncSubscribers
    assert asyncio.iscoroutine(receiver.discovery_coro)
    # test the number of tasks (one per Supvisors instance, local instance excepted, + stop, + puller, + discovery)
    assert len(supvisors.mapper.instances) == 7
    tasks = receiver.get_tasks()
    try:
        assert all(asyncio.iscoroutine(x) for x in tasks)
        assert len(tasks) == len(supvisors.mapper.instances) + 2
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
