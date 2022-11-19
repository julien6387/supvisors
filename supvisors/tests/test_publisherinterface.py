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

from supvisors.publisherinterface import *


@pytest.fixture
def zmq_import():
    return pytest.importorskip('zmq')


@pytest.fixture
def zmq_fail_import(mocker):
    """ Mock ImportError on optional lxml if installed to force ElementTree testing. """
    mocker.patch.dict('sys.modules', {'zmq': None})


def test_interface():
    """ Test the EventPublisherInterface abstract class. """
    intf = EventPublisherInterface()
    with pytest.raises(NotImplementedError):
        intf.close()
    with pytest.raises(NotImplementedError):
        intf.send_supvisors_status({})
    with pytest.raises(NotImplementedError):
        intf.send_instance_status({})
    with pytest.raises(NotImplementedError):
        intf.send_application_status({})
    with pytest.raises(NotImplementedError):
        intf.send_process_event('10.0.0.1', {})
    with pytest.raises(NotImplementedError):
        intf.send_process_status({})


def test_create_external_publisher_none(supvisors):
    """ Test the create_external_publisher function with no event link selected. """
    assert create_external_publisher(supvisors) is None


def test_create_external_publisher_zmq_fail(zmq_import, zmq_fail_import, supvisors):
    """ Test the create_external_publisher function with zmq event link but not installed. """
    supvisors.options.event_link = EventLinks.ZMQ
    # test inclusion of Supvisors into Supervisor
    assert create_external_publisher(supvisors) is None


def test_create_external_publisher_zmq(zmq_import, supvisors):
    """ Test the make_supvisors_rpcinterface function. """
    from supvisors.supvisorszmq import EventPublisher
    supvisors.options.event_link = EventLinks.ZMQ
    # test inclusion of Supvisors into Supervisor
    instance = create_external_publisher(supvisors)
    assert isinstance(instance, EventPublisher)
