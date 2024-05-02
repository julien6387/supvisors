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

import time
from socket import gethostname, gethostbyaddr

import pytest

from supvisors.internal_com.multicast import *


@pytest.fixture
def discovery(supvisors):
    """ Create the MulticastSender instance. """
    # set the options
    supvisors.options.multicast_group = '239.0.0.1', 7777
    supvisors.options.multicast_ttl = 1
    # create the instance
    disco = SupvisorsDiscovery(supvisors)
    # wait for thread to start
    time.sleep(1)
    assert disco.mc_receiver.is_alive()
    yield disco
    disco.stop()


def test_multicast(supvisors, discovery):
    """ Test the Supvisors Multicast in one single test. """
    hostname, aliases, ip_addresses = gethostbyaddr(gethostname())
    # send event
    payload = {'when': 1234, 'identifier': '10.0.0.1:10000', 'nick_identifier': 'rocky51',
               'http_port': 10000, 'ip_addresses': ip_addresses}
    discovery.mc_sender.send_discovery_event(payload)
    # check output
    time.sleep(1.0)
    call_args_list = supvisors.rpc_handler.push_notification.call_args_list
    assert len(call_args_list) == 1
    message = call_args_list[0][0][0]
    assert type(message) is tuple
    assert len(message) == 2
    source, event_body = message
    assert source[0] == '10.0.0.1:10000'
    assert source[1] == 'rocky51'
    assert type(source[2]) is tuple
    assert len(source[2]) == 2
    assert source[2][1] == 10000
    assert event_body == (NotificationHeaders.DISCOVERY.value, ())
    supvisors.rpc_handler.push_notification.reset_mock()
    # send event that does not fit
    payload = {'when': 1234, 'identifier': '10.0.0.1:10000', 'nick_identifier': 'rocky51',
               'http_port': 10000, 'ip_addresses': []}
    discovery.mc_sender.send_discovery_event(payload)
    assert len(call_args_list) == 1
    message = call_args_list[0][0][0]
    assert type(message) is tuple
    assert len(message) == 2
    source, event_body = message
    assert source[0] == '10.0.0.1:10000'
    assert source[1] == 'rocky51'
    assert type(source[2]) is tuple
    assert len(source[2]) == 2
    assert source[2][1] == 10000
    assert event_body == (NotificationHeaders.DISCOVERY.value, ())


# testing exception cases (by line number)
def test_emitter_send_exception(discovery):
    """ Test the sendto exception of the MulticastSender.
    The aim is to hit the lines 64-66 in MulticastSender.emit_message.
    Checked ok with debugger.
    """
    discovery.stop()
    discovery.mc_sender.send_discovery_event({})


def test_receiver_bind_exception(supvisors):
    """ Test the bind exception of the MulticastReceiver (use wrong IP).
    The aim is to hit the lines 131-134 in MulticastReceiver.open_multicast.
    Checked ok with debugger.
    """
    mc_receiver = MulticastReceiver(('localhost', -1), None, None, supvisors.logger)
    assert mc_receiver.socket is None
    mc_receiver.open_multicast()
    assert mc_receiver.socket is None


def test_receiver_membership_exception(supvisors):
    """ Test the add membership exception of the MulticastReceiver (use wrong IP).
    The aim is to hit the lines 145-148 in MulticastReceiver.open_multicast.
    Checked ok with debugger.
    """
    # test illegal address
    mc_receiver = MulticastReceiver(('localhost', 7777), 'localhost', None, supvisors.logger)
    assert mc_receiver.socket is None
    mc_receiver.open_multicast()
    assert mc_receiver.socket is None
    # test wrong interface
    mc_receiver = MulticastReceiver(('239.0.0.1', 7777), '10.0.0', None, supvisors.logger)
    assert mc_receiver.socket is None
    mc_receiver.open_multicast()
    assert mc_receiver.socket is None
