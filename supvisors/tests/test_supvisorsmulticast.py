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

from socket import gethostbyname, gethostname, socketpair

import pytest

from supvisors.supvisorsmulticast import *
from supvisors.ttypes import DeferredRequestHeaders

local_ip = gethostbyname(gethostname())


@pytest.fixture
def mc(supvisors):
    """ Create the SupvisorsSockets instance. """
    supvisors.options.multicast_group = '239.0.0.1', 7777
    socks = SupvisorsMulticast(supvisors)
    yield socks
    socks.stop()
    socks.receiver.close()


def check_sockets(receiver: MulticastReceiver,
                  request: Any,
                  notification: Any,
                  emitter_identifier: Optional[str]):
    """ Check that requests or notifications have been received as expected.
    Poll timeout is 100ms, so this method waits up to 3 seconds to get the messages expected. """
    got_expected_request, got_expected_notification = False, False
    for _ in range(30):
        requests_socket, external_events_sockets = receiver.poll()
        # test request part
        assert not requests_socket or request
        if requests_socket:
            assert receiver.read_socket(receiver.puller_sock) == ('', request)
            got_expected_request = True
        # test notification part
        messages = receiver.read_fds(external_events_sockets)
        for peer, (msg_type, (identifier, msg_body)) in messages:
            assert peer[0] == local_ip
            # test events
            assert identifier == emitter_identifier
            assert msg_type == notification[0]
            assert msg_body == notification[1]
            got_expected_notification = True
        # send heartbeats
        receiver.manage_heartbeat()
        # exit for loop if request received
        if got_expected_request and not notification:
            break
        # exit for loop if notification received
        if got_expected_notification and not request:
            break
    # final check
    assert not request or got_expected_request
    assert not notification or got_expected_notification


def test_global_normal(supvisors, mc):
    """ Test the Supvisors Multicast in one single test. """
    # initial check for connectable instances
    # assert sorted(mc.receiver.instances.keys()) == sorted(supvisors.supvisors_mapper.instances.keys())
    # the subscriber has connected the local publisher instance
    local_identifier = supvisors.supvisors_mapper.local_identifier
    #assert list(mc.receiver.subscribers.keys()) == [local_identifier]
    #client_sock, hb_sent, hb_recv = mc.receiver.subscribers[local_identifier]
    #assert isinstance(client_sock, socket)
    # poll during 3 seconds: nothing sent but heartbeat
    check_sockets(mc.receiver, None, None, local_identifier)
    # test push / subscribe for CHECK_INSTANCE
    mc.pusher.send_check_instance('10.0.0.1')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.CHECK_INSTANCE.value, ['10.0.0.1', ]],
                  None, local_identifier)
    # test push / subscribe for ISOLATE_INSTANCES
    mc.pusher.send_isolate_instances(['10.0.0.1', '10.0.0.2'])
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.ISOLATE_INSTANCES.value, ['10.0.0.1', '10.0.0.2']],
                  None, local_identifier)
    # test push / subscribe for START_PROCESS
    mc.pusher.send_start_process('10.0.0.1', 'group:name', 'extra args')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.START_PROCESS.value, ['10.0.0.1', 'group:name', 'extra args']],
                  None, local_identifier)
    # test push / subscribe for STOP_PROCESS
    mc.pusher.send_stop_process('10.0.0.1', 'group:name')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.STOP_PROCESS.value, ['10.0.0.1', 'group:name']],
                  None, local_identifier)
    # test push / subscribe for RESTART
    mc.pusher.send_restart('10.0.0.1')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.RESTART.value, ['10.0.0.1', ]],
                  None, local_identifier)
    # test push / subscribe for SHUTDOWN
    mc.pusher.send_shutdown('10.0.0.1')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.SHUTDOWN.value, ['10.0.0.1', ]],
                  None, local_identifier)
    # test push / subscribe for RESTART_SEQUENCE
    mc.pusher.send_restart_sequence('10.0.0.1')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.RESTART_SEQUENCE.value, ['10.0.0.1', ]],
                  None, local_identifier)
    # test push / subscribe for RESTART_ALL
    mc.pusher.send_restart_all('10.0.0.1')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.RESTART_ALL.value, ['10.0.0.1', ]],
                  None, local_identifier)
    # test push / subscribe for SHUTDOWN_ALL
    mc.pusher.send_shutdown_all('10.0.0.1')
    check_sockets(mc.receiver,
                  [DeferredRequestHeaders.SHUTDOWN_ALL.value, ['10.0.0.1', ]],
                  None, local_identifier)
    # test publish / subscribe for HEARTBEAT (not yet)
    # test publish / subscribe for TICK
    mc.emitter.send_tick_event({'when': 1234})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.TICK.value, {'when': 1234}],
                  local_identifier)
    # test publish / subscribe for PROCESS
    mc.emitter.send_process_state_event({'namespec': 'dummy_group:dummy_name', 'state': 'running'})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.PROCESS.value, {'namespec': 'dummy_group:dummy_name', 'state': 'running'}],
                  local_identifier)
    # test publish / subscribe for PROCESS_ADDED
    mc.emitter.send_process_added_event({'namespec': 'dummy_group:dummy_name'})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.PROCESS_ADDED.value, {'namespec': 'dummy_group:dummy_name'}],
                  local_identifier)
    # test publish / subscribe for PROCESS_REMOVED
    mc.emitter.send_process_removed_event({'namespec': 'dummy_group:dummy_name'})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.PROCESS_REMOVED.value, {'namespec': 'dummy_group:dummy_name'}],
                  local_identifier)
    # test publish / subscribe for PROCESS_DISABILITY
    mc.emitter.send_process_disability_event({'name': 'dummy_name', 'disabled': True})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.PROCESS_DISABILITY.value, {'name': 'dummy_name', 'disabled': True}],
                  local_identifier)
    # test publish / subscribe for HOST_STATISTICS
    mc.emitter.send_host_statistics({'cpu': 25.3, 'mem': 12.5})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.HOST_STATISTICS.value, {'cpu': 25.3, 'mem': 12.5}],
                  local_identifier)
    # test publish / subscribe for PROCESS_STATISTICS
    mc.emitter.send_process_statistics({'dummy_process': {'cpu': 25.3, 'mem': 12.5}})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.PROCESS_STATISTICS.value, {'dummy_process': {'cpu': 25.3, 'mem': 12.5}}],
                  local_identifier)
    # test publish / subscribe for STATE
    mc.emitter.send_state_event({'state': 'operational', 'mode': 'starting'})
    check_sockets(mc.receiver, None,
                  [InternalEventHeaders.STATE.value, {'state': 'operational', 'mode': 'starting'}],
                  local_identifier)
    # test subscriber disconnect and check that nothing is received anymore
    #mc.receiver.disconnect_subscriber([local_identifier])
    #assert mc.receiver.subscribers == {}
    #assert local_identifier not in mc.receiver.instances
    # check that nothing is received anymore by the subscribers
    #mc.emitter.send_state_event({'state': 'operational', 'mode': 'starting'})
    #check_sockets(mc.receiver, None, None, None)


def test_emitter_send_exception(mc):
    """ Test the sendto exception of the MulticastSender. """
    mc.emitter.close()
    mc.emitter.send_tick_event({})


def test_receiver_bind_exception(supvisors):
    """ Test the bind exception of the MulticastReceiver (use wrong IP). """
    push_sock, pull_sock = socketpair()
    sender = MulticastReceiver(pull_sock, ('10.0.0', 1234), supvisors.logger)
    assert not sender.socket
