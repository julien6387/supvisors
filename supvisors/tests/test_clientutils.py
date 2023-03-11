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


from unittest.mock import call

from supervisor.loggers import Logger, LevelsByName

from supvisors.client.clientutils import create_logger


def test_create_logger(mocker):
    """ Test the create_logger method. """
    mocked_stdout = mocker.patch('supervisor.loggers.handle_stdout')
    mocked_file = mocker.patch('supervisor.loggers.handle_file')
    # test default
    default_format = '%(asctime)s;%(levelname)s;%(message)s\n'
    logger = create_logger()
    assert isinstance(logger, Logger)
    assert logger.level == LevelsByName.INFO
    assert mocked_stdout.call_args_list == [call(logger, default_format)]
    assert mocked_file.call_args_list == [call(logger, r'subscriber.log', default_format, True, 10485760, 1)]
    mocker.resetall()
    # test with parameters
    new_format = '%(asctime)s %(message)s'
    logger = create_logger('/tmp/client.log', LevelsByName.CRIT, new_format, False, 1024, 10, False)
    assert isinstance(logger, Logger)
    assert logger.level == LevelsByName.CRIT
    assert not mocked_stdout.called
    assert mocked_file.call_args_list == [call(logger, '/tmp/client.log', new_format, False, 1024, 10)]
