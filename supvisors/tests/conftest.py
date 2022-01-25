#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2021 Julien LE CLEACH
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

from supvisors.application import ApplicationRules, ApplicationStatus
from supvisors.process import ProcessRules, ProcessStatus
from unittest.mock import Mock

from .base import DummySupervisor, MockedSupvisors, any_process_info


# Easy Application / Process creation
def create_process(info, supvisors):
    """ Create a ProcessStatus from a payload. """
    return ProcessStatus(info['group'], info['name'], ProcessRules(supvisors), supvisors)


def create_any_process(supvisors):
    return create_process(any_process_info(), supvisors)


def create_application(application_name, supvisors):
    """ Create an ApplicationStatus. """
    return ApplicationStatus(application_name, ApplicationRules(supvisors), supvisors)


# fixture for common global structures
@pytest.fixture
def supervisor():
    return DummySupervisor()


@pytest.fixture
def supvisors():
    return MockedSupvisors()


# Easy XHTML element creation
def create_element(mid_map=None):
    mock = Mock(attrib={'class': ''}, **{'findmeld.side_effect': lambda x: mid_map[x] if mid_map else None,
                                         'repeat.return_value': None})

    def reset_all():
        mock.attrib = {'class': ''}
        mock.reset_mock()
        if mid_map:
            for mid in mid_map.values():
                mid.reset_all()
    mock.reset_all = reset_all
    return mock
