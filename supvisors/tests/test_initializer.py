#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

from unittest.mock import Mock

import pytest

from supvisors.initializer import *
from supvisors.statscollector import ProcessStatisticsCollector, instant_host_statistics
from supvisors.statscompiler import HostStatisticsCompiler, ProcStatisticsCompiler
from .base import DummySupervisor


def test_creation(mocker):
    """ Test the values set at construction. """
    mocked_parser = mocker.patch('supvisors.initializer.Parser', return_value='Parser')
    mocked_srv_options = Mock(procnumbers={})
    mocked_options = mocker.patch('supvisors.initializer.SupvisorsServerOptions', return_value=mocked_srv_options)
    # create the instance to test, using default empty configuration
    supv = Supvisors(DummySupervisor())
    # test calls
    assert mocked_options.called
    assert mocked_parser.called
    # test instances
    assert supv.internal_com is None
    assert supv.external_publisher is None
    assert isinstance(supv.options, SupvisorsOptions)
    assert mocked_srv_options.realize.called
    assert isinstance(supv.logger, Logger)
    assert isinstance(supv.supervisor_data, SupervisorData)
    assert isinstance(supv.mapper, SupvisorsMapper)
    assert supv.host_collector is instant_host_statistics
    assert isinstance(supv.process_collector, ProcessStatisticsCollector)
    assert isinstance(supv.context, Context)
    assert isinstance(supv.starter, Starter)
    assert isinstance(supv.stopper, Stopper)
    assert isinstance(supv.host_compiler, HostStatisticsCompiler)
    assert isinstance(supv.process_compiler, ProcStatisticsCompiler)
    assert isinstance(supv.fsm, FiniteStateMachine)
    assert supv.parser == 'Parser'
    assert isinstance(supv.listener, SupervisorListener)


def test_create_logger():
    """ Test the create_logger method. """
    # create Supvisors instance
    supervisor = DummySupervisor()
    # test AUTO logfile
    logger_config = get_logger_configuration()
    logger_config['logfile'] = Automatic
    assert create_logger(supervisor, logger_config) is supervisor.options.logger
    # test defined logfile
    logger_config['logfile'] = '/tmp/dummy.log'
    logger = create_logger(supervisor, logger_config)
    assert logger is not supervisor.options.logger


def test_identifier_exception(mocker):
    """ Test the values set at construction. """
    mocker.patch('supvisors.initializer.SupvisorsServerOptions')
    mocker.patch('supvisors.initializer.SupvisorsMapper.configure', side_effect=ValueError)
    # create Supvisors instance
    supervisord_instance = DummySupervisor()
    # test that local node exception raises a failure to Supervisor
    with pytest.raises(ValueError):
        Supvisors(supervisord_instance)


def test_psutil_exception(mocker):
    """ Test the values set at construction. """
    mocker.patch('supvisors.initializer.SupvisorsServerOptions')
    mocker.patch.dict('sys.modules', {'supvisors.statscollector': None})
    # create Supvisors instance
    supvisors = Supvisors(DummySupervisor())
    # test that parser exception is accepted
    assert supvisors.host_collector is None
    assert supvisors.process_collector is None


def test_parser_exception(mocker):
    """ Test the values set at construction. """
    mocker.patch('supvisors.initializer.Parser', side_effect=Exception)
    mocker.patch('supvisors.initializer.SupvisorsServerOptions')
    # create Supvisors instance
    supvisors = Supvisors(DummySupervisor())
    # test that parser exception is accepted
    assert supvisors.parser is None


def test_supvisors_init():
    """ Just import supvisors to test __init__.py file. """
    import supvisors
    assert supvisors.__name__ == 'supvisors'
