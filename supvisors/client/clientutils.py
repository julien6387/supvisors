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

from supervisor import loggers
from supervisor.loggers import LevelsByName


def create_logger(logfile=r'subscriber.log', loglevel=LevelsByName.INFO,
                  fmt='%(asctime)s;%(levelname)s;%(message)s\n',
                  rotating=True, maxbytes=10 * 1024 * 1024, backups=1, stdout=True):
    """ Return a simple Supervisor logger. """
    logger = loggers.getLogger(loglevel)
    if stdout:
        loggers.handle_stdout(logger, fmt)
    loggers.handle_file(logger, logfile, fmt, rotating, maxbytes, backups)
    return logger
