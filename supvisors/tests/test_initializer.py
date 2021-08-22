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

import pytest

from supervisor.loggers import Logger
from unittest.mock import Mock

from .base import DummySupervisor, DummyOptions


def test_creation(mocker):
    """ Test the values set at construction. """
    mocked_parser = mocker.patch('supvisors.initializer.Parser', return_value='Parser')
    mocked_logger = mocker.patch('supvisors.initializer.Supvisors.create_logger', return_value=Mock(spec=Logger))
    mocked_supv_options = DummyOptions()
    mocked_srv_options = Mock(supvisors_options=mocked_supv_options)
    mocked_options = mocker.patch('supvisors.initializer.SupvisorsServerOptions', return_value=mocked_srv_options)
    # create the instance to test
    from supvisors.initializer import (AddressMapper, Context, Supvisors, SupervisordSource, Starter, Stopper,
                                       StatisticsCompiler, FiniteStateMachine, SupervisorListener)
    supv = Supvisors(DummySupervisor())
    # test calls
    assert mocked_options.called
    assert mocked_logger.called
    assert mocked_parser.called
    # test instances
    assert supv.options is not None
    assert mocked_srv_options.realize.called
    assert supv.logger is not None
    assert supv.info_source is not None
    assert isinstance(supv.info_source, SupervisordSource)
    assert supv.address_mapper is not None
    assert isinstance(supv.address_mapper, AddressMapper)
    assert supv.context is not None
    assert isinstance(supv.context, Context)
    assert supv.starter is not None
    assert isinstance(supv.starter, Starter)
    assert supv.stopper is not None
    assert isinstance(supv.stopper, Stopper)
    assert supv.statistician is not None
    assert isinstance(supv.statistician, StatisticsCompiler)
    assert supv.fsm is not None
    assert isinstance(supv.fsm, FiniteStateMachine)
    assert supv.parser == 'Parser'
    assert supv.listener is not None
    assert isinstance(supv.listener, SupervisorListener)


def test_create_logger(mocker):
    """ Test the create_logger method. """
    from supervisor.datatypes import Automatic
    from supvisors.initializer import Supvisors
    # create mocked supvisors options
    mocked_options = Mock(supvisors_options=DummyOptions())
    mocker.patch('supvisors.initializer.SupvisorsServerOptions', return_value=mocked_options)
    # create Supvisors instance
    supervisord = DummySupervisor()
    supvisors = Supvisors(supervisord)
    # test AUTO logfile
    mocked_options.supvisors_options.logfile = Automatic
    assert supvisors.create_logger(supervisord) is supervisord.options.logger
    # for the following, supervisord must be silent because of logger
    # for unknown reason test_initializer got this exception
    # ValueError: I/O operation on closed file
    supervisord.options.silent = True
    # test defined logfile
    mocked_options.supvisors_options.logfile = '/tmp/dummy.log'
    logger = supvisors.create_logger(supervisord)
    assert logger is not supervisord.options.logger


def test_address_exception(mocker):
    """ Test the values set at construction. """
    mocker.patch('supvisors.initializer.loggers')
    mocker.patch('supvisors.initializer.SupvisorsServerOptions')
    from supvisors.initializer import Supvisors, Faults, RPCError
    # create Supvisors instance
    supervisord = DummySupervisor()
    # patches Faults codes
    setattr(Faults, 'SUPVISORS_CONF_ERROR', 777)
    # test that local address exception raises a failure to Supervisor
    with pytest.raises(RPCError):
        Supvisors(supervisord)


def test_parser_exception(mocker):
    """ Test the values set at construction. """
    mocker.patch('supvisors.initializer.Parser', side_effect=Exception)
    mocker.patch('supvisors.initializer.Supvisors.create_logger', return_value=Mock(spec=Logger))
    mocked_supv_options = DummyOptions()
    mocked_srv_options = Mock(supvisors_options=mocked_supv_options)
    mocker.patch('supvisors.initializer.SupvisorsServerOptions', return_value=mocked_srv_options)
    # create Supvisors instance
    from supvisors.initializer import Supvisors
    supvisors = Supvisors(DummySupervisor())
    # test that parser exception is accepted
    assert supvisors.parser is None


def test_supvisors_init():
    """ Just import supvisors to test __init__.py file. """
    import supvisors
    assert supvisors.__name__ == 'supvisors'
