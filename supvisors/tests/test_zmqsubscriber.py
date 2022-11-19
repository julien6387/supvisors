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

from supvisors.client.zmqsubscriber import *
from unittest.mock import call, Mock
from zmq import ZMQError


def test_create_logger(mocker):
    """ Test the create_logger method. """
    mocked_stdout = mocker.patch('supervisor.loggers.handle_stdout')
    mocked_file = mocker.patch('supervisor.loggers.handle_file')
    # test default
    default_format = '%(asctime)s;%(levelname)s;%(message)s\n'
    logger = create_logger()
    assert isinstance(logger, loggers.Logger)
    assert logger.level == LevelsByName.INFO
    assert mocked_stdout.call_args_list == [call(logger, default_format)]
    assert mocked_file.call_args_list == [call(logger, r'subscriber.log', default_format, True, 10485760, 1)]
    mocker.resetall()
    # test with parameters
    new_format = '%(asctime)s %(message)s'
    logger = create_logger('/tmp/client.log', LevelsByName.CRIT, new_format, False, 1024, 10, False)
    assert isinstance(logger, loggers.Logger)
    assert logger.level == LevelsByName.CRIT
    assert not mocked_stdout.called
    assert mocked_file.call_args_list == [call(logger, '/tmp/client.log', new_format, False, 1024, 10)]


@pytest.fixture
def context():
    return zmq.Context.instance()


@pytest.fixture
def logger():
    return Mock(spec=loggers.Logger)


@pytest.fixture
def interface(context, logger):
    intf = SupvisorsZmqEventInterface(context, 7777, logger)
    yield intf
    intf.subscriber.close()


def test_creation(context, logger, interface):
    """ Test the initialization of the SupvisorsEventInterface. """
    assert isinstance(interface, threading.Thread)
    assert interface.zmq_context is context
    assert interface.event_port == 7777
    assert interface.logger is logger
    assert isinstance(interface.subscriber, EventSubscriber)
    assert isinstance(interface.stop_event, threading.Event)


def test_stop(interface):
    """ Test the SupvisorsEventInterface.stop method. """
    assert not interface.stop_event.is_set()
    interface.stop()
    assert interface.stop_event.is_set()


def test_run_nothing(mocker, context, logger, interface):
    """ Test the behavior of the thread loop when nothing to poll. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    logger.reset_mock()
    # test run method when nothing to poll
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop')]
    assert not logger.debug.called
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_no_pollin(mocker, context, logger, interface):
    """ Test the behavior of the thread loop when nothing to poll in. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLOUT})
    logger.reset_mock()
    # test run method when nothing to poll
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop')]
    assert not logger.debug.called
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_error(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with exception on receive. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive', side_effect=ZMQError(10, 'failed'))
    logger.reset_mock()
    # test run method with exception on receive
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert logger.error.call_args_list == [call('SupvisorsEventInterface.run: failed to get data from subscriber:'
                                                ' failed')]
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_unexpected_event(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with Supvisors status message. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive',
                        return_value=('unexpected', 'supvisors payload'))
    logger.reset_mock()
    # test run method with Supvisors status message
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert logger.error.call_args_list == [call('SupvisorsEventInterface.run: unexpected event type unexpected')]
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_supvisors(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with Supvisors status message. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive',
                        return_value=(EventHeaders.SUPVISORS.value, 'supvisors payload'))
    logger.reset_mock()
    # test run method with Supvisors status message
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop'),
                                          call('SupvisorsEventInterface.on_supvisors_status:'
                                               ' got Supvisors Status message: supvisors payload')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_instance(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with Instance status message. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive',
                        return_value=(EventHeaders.INSTANCE.value, 'instance payload'))
    logger.reset_mock()
    # test run method with Instance status message
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop'),
                                          call('SupvisorsEventInterface.on_instance_status:'
                                               ' got Instance Status message: instance payload')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_application(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with Application status message. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive',
                        return_value=(EventHeaders.APPLICATION.value, 'application payload'))
    logger.reset_mock()
    # test run method with Application status message
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop'),
                                          call('SupvisorsEventInterface.on_application_status:'
                                               ' got Application Status message: application payload')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_process(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with Process status message. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive',
                        return_value=(EventHeaders.PROCESS_STATUS.value, 'process payload'))
    logger.reset_mock()
    # test run method with Process status message
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop'),
                                          call('SupvisorsEventInterface.on_process_status:'
                                               ' got Process Status message: process payload')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed


def test_run_receive_event(mocker, context, logger, interface):
    """ Test the behavior of the thread loop with Process event message. """
    # patch the context
    mocker.patch.object(interface.stop_event, 'is_set', side_effect=[False, True])
    mocker.patch('zmq.Poller.poll', return_value={interface.subscriber.socket: zmq.POLLIN})
    mocker.patch.object(interface.subscriber, 'receive',
                        return_value=(EventHeaders.PROCESS_EVENT.value, 'event payload'))
    logger.reset_mock()
    # test run method with Process event message
    interface.run()
    assert logger.info.call_args_list == [call('SupvisorsEventInterface.run: entering main loop'),
                                          call('SupvisorsEventInterface.on_process_event:'
                                               ' got Process Event message: event payload')]
    assert logger.debug.call_args_list == [call('SupvisorsEventInterface.run: got message on subscriber')]
    assert not logger.error.called
    assert logger.warn.call_args_list == [call('SupvisorsEventInterface.run: exiting main loop')]
    assert interface.subscriber.socket.closed
