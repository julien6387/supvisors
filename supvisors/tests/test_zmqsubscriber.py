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

import pytest
pytest.importorskip('zmq', reason='cannot test as optional pyzmq is not installed')

from unittest.mock import call, Mock

from supvisors.client.zmqsubscriber import *


@pytest.fixture
def context():
    return zmq.asyncio.Context.instance()


@pytest.fixture
def logger():
    return Mock(spec=Logger)


@pytest.fixture
def interface(context, logger):
    intf = SupvisorsZmqEventInterface(context, 'localhost', 7777, logger)
    yield intf
    intf.stop()


def test_creation(context, logger, interface):
    """ Test the initialization of the SupvisorsZmqEventInterface. """
    assert isinstance(interface, EventSubscriberInterface)
    assert isinstance(interface, ZmqEventSubscriber)
    assert interface.zmq_context is context
    assert interface.intf is interface
    assert interface.node_name == 'localhost'
    assert interface.event_port == 7777
    assert interface.logger is logger


def test_on_receive(interface, logger):
    """ Dummy tests about logging when receiving messages from Supvisors. """
    # test reception of Supvisors status message
    interface.on_supvisors_status('supvisors payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_supvisors_status:'
                                               ' got Supvisors Status message: supvisors payload')]
    logger.info.reset_mock()
    # test reception of Supvisors Instance status message
    interface.on_instance_status('instance payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_instance_status:'
                                               ' got Instance Status message: instance payload')]
    logger.info.reset_mock()
    # test reception of Supvisors Application status message
    interface.on_application_status('application payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_application_status:'
                                               ' got Application Status message: application payload')]
    logger.info.reset_mock()
    # test reception of Supvisors Process event message
    interface.on_process_event('process event payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_process_event:'
                                               ' got Process Event message: process event payload')]
    logger.info.reset_mock()
    # test reception of Supvisors Process status message
    interface.on_process_status('process payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_process_status:'
                                               ' got Process Status message: process payload')]
    logger.info.reset_mock()
    # test reception of Supvisors Application status message
    interface.on_host_statistics('host statistics payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_host_statistics:'
                                               ' got Host Statistics message: host statistics payload')]
    logger.info.reset_mock()
    # test reception of Supvisors Application status message
    interface.on_process_statistics('process statistics payload')
    assert logger.info.call_args_list == [call('SupvisorsZmqEventInterface.on_process_statistics:'
                                               ' got Process Statistics message: process statistics payload')]
    logger.info.reset_mock()

