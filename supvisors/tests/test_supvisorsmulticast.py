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

import pytest

from supvisors.internal_com.multicast import *
from supvisors.ttypes import InternalEventHeaders


@pytest.fixture
def mc_sender(supvisors):
    """ Create the MulticastSender instance. """
    sender = MulticastSender(supvisors.mapper.local_identifier, ('239.0.0.1', 7777), 0, supvisors.logger)
    yield sender
    sender.close()


@pytest.mark.asyncio
async def test_multicast(supvisors, mc_sender):
    """ Test the Supvisors Multicast in one single test. """
    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    supvisors.options.multicast_group = '239.0.0.1', 7777

    async def sender_task():
        """ test of the multicast sender """
        await asyncio.sleep(0.5)
        mc_sender.send_tick_event({'when': 1234})
        await asyncio.sleep(1.0)
        stop_event.set()

    async def check_output():
        """ test of the receiver output """
        expected = [InternalEventHeaders.TICK.value, [supvisors.mapper.local_identifier, {'when': 1234}]]
        message = await asyncio.wait_for(queue.get(), 2.0)
        # first part of the message is platform-dependent, so avoid to test it
        assert message[1] == expected

    # handle_puller can loop forever, so add a wait_for just in case something goes wrong
    await asyncio.gather(sender_task(),
                         asyncio.wait_for(handle_mc_receiver(queue, stop_event, supvisors), 4.0),
                         check_output())


# testing exception cases (by line number)
def test_emitter_send_exception(mc_sender):
    """ Test the sendto exception of the MulticastSender.
    The aim is to hit the lines 65-67 in MulticastSender.emit_message.
    Checked ok with debugger.
    """
    mc_sender.close()
    mc_sender.send_tick_event({})


@pytest.mark.asyncio
async def test_receiver_bind_exception(supvisors):
    """ Test the bind exception of the MulticastReceiver (use wrong IP).
    The aim is to hit the lines 100-101 in handle_mc_receiver.
    Checked ok with debugger.
    """
    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    supvisors.options.multicast_group = 'localhost', -1

    await asyncio.wait_for(handle_mc_receiver(queue, stop_event, supvisors), 2.0)


@pytest.mark.asyncio
async def test_receiver_membership_exception(supvisors):
    """ Test the bind exception of the MulticastReceiver (use wrong IP).
    The aim is to hit the lines 111-113 in handle_mc_receiver.
    Checked ok with debugger.
    """
    queue = asyncio.Queue()
    stop_event = asyncio.Event()
    supvisors.options.multicast_group = '239.0.0.1', 7777
    supvisors.options.multicast_interface = '10.0.0'

    await asyncio.wait_for(handle_mc_receiver(queue, stop_event, supvisors), 2.0)
