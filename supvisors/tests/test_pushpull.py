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
    puller = AsyncRpcPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        pusher = RpcPusher(push_pull[0], supvisors)
        assert pusher.logger is supvisors.logger
        # 1. test requests
        # test push CHECK_INSTANCE
        pusher.send_check_instance('10.0.0.1')
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
        # 2. test publications
        # test push TICK
        pusher.send_tick_event({'when': 1234})
        # test push PROCESS
        pusher.send_process_state_event({'name': 'dummy', 'state': 'RUNNING'})
        # test push PROCESS_ADDED
        pusher.send_process_added_event({'name': 'dummy'})
        # test push PROCESS_REMOVED
        pusher.send_process_removed_event({'name': 'dummy'})
        # test push PROCESS_DISABILITY
        pusher.send_process_disability_event({'name': 'dummy_program'})
        # test push HOST_STATISTICS
        pusher.send_host_statistics({'cpu': 1.0})
        # test push PROCESS_STATISTICS
        pusher.send_process_statistics({'dummy_process': {'cpu': 1.0}})
        # test push STATE
        pusher.send_state_event({'state': 'INIT'})
        # test timeout on reception
        await asyncio.sleep(1.5)
        event.set()

    async def check_output():
        """ test of the puller output """
        # 1. test requests
        # test pull CHECK_INSTANCE
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.CHECK_INSTANCE.value, ['10.0.0.1', ]]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull START_PROCESS
        expected = [InternalEventHeaders.REQUEST.value,
                    [RequestHeaders.START_PROCESS.value, ['10.0.0.1', 'group:name', 'extra args']]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull STOP_PROCESS
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.STOP_PROCESS.value, ['10.0.0.1', 'group:name']]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull RESTART
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.RESTART.value, ['10.0.0.1', ]]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull SHUTDOWN
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.SHUTDOWN.value, ['10.0.0.1', ]]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull RESTART_SEQUENCE
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.RESTART_SEQUENCE.value, ['10.0.0.1', ]]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull RESTART_ALL
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.RESTART_ALL.value, ['10.0.0.1', ]]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull SHUTDOWN_ALL
        expected = [InternalEventHeaders.REQUEST.value, [RequestHeaders.SHUTDOWN_ALL.value, ['10.0.0.1', ]]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # 2. test publications
        # test pull TICK
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.TICK.value, {'when': 1234}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull PROCESS
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.PROCESS.value, {'name': 'dummy', 'state': 'RUNNING'}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull PROCESS_ADDED
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.PROCESS_ADDED.value, {'name': 'dummy'}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull PROCESS_REMOVED
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.PROCESS_REMOVED.value, {'name': 'dummy'}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull PROCESS_DISABILITY
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.PROCESS_DISABILITY.value, {'name': 'dummy_program'}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull HOST_STATISTICS
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.HOST_STATISTICS.value, {'cpu': 1.0}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull PROCESS_STATISTICS
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.PROCESS_STATISTICS.value,{'dummy_process': {'cpu': 1.0}}]]
        assert await asyncio.wait_for(queue.get(), 1.0) == expected
        # test pull STATE
        expected = [InternalEventHeaders.PUBLICATION.value,
                    [PublicationHeaders.STATE.value, {'state': 'INIT'}]]
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
    puller = AsyncRpcPuller(queue, event, supvisors)

    async def pusher_task():
        """ test of the pusher """
        pusher = RpcPusher(push_pull[0], supvisors)
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
    puller = AsyncRpcPuller(queue, event, supvisors)

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
    pusher = RpcPusher(push_pull[0], supvisors)
    push_pull[0].close()
    pusher.send_shutdown('10.0.0.1')
