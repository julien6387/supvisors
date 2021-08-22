#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2016 Julien LE CLEACH
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

import os

from enum import Enum

from supervisor.options import ServerOptions
from supervisor.web import VIEWS, StatusView
from supervisor.xmlrpc import Faults

from .initializer import Supvisors
from .rpcinterface import RPCInterface
from .viewapplication import ApplicationView
from .viewhandler import ViewHandler
from .viewhostaddress import HostAddressView
from .viewimage import *
from .viewprocaddress import ProcAddressView
from .viewsupvisors import SupvisorsView


# Supvisors related faults
class SupvisorsFaults(Enum):
    SUPVISORS_CONF_ERROR, BAD_SUPVISORS_STATE, BAD_ADDRESS, BAD_STRATEGY, BAD_LEVEL, BAD_EXTRA_ARGUMENTS = range(6)


FAULTS_OFFSET = 100


def expand_faults():
    """ Expand supervisord Fault definition. """
    for x in SupvisorsFaults:
        setattr(Faults, x.name, x.value + FAULTS_OFFSET)


def update_views():
    """ Trick to replace Supervisor main page. """
    # replace Supervisor main entry
    here = os.path.abspath(os.path.dirname(__file__))
    # set main page
    VIEWS['index.html'] = {'template': os.path.join(here, 'ui/index.html'), 'view': SupvisorsView}
    # set address /processpage
    VIEWS['procaddress.html'] = {'template': os.path.join(here, 'ui/procaddress.html'), 'view': ProcAddressView}
    # set address/host page
    VIEWS['hostaddress.html'] = {'template': os.path.join(here, 'ui/hostaddress.html'), 'view': HostAddressView}
    # set application page
    VIEWS['application.html'] = {'template': os.path.join(here, 'ui/application.html'), 'view': ApplicationView}
    # set fake page to export images
    VIEWS['process_cpu.png'] = {'template': None, 'view': ProcessCpuImageView}
    VIEWS['process_mem.png'] = {'template': None, 'view': ProcessMemoryImageView}
    VIEWS['address_cpu.png'] = {'template': None, 'view': AddressCpuImageView}
    VIEWS['address_mem.png'] = {'template': None, 'view': AddressMemoryImageView}
    VIEWS['address_io.png'] = {'template': None, 'view': AddressNetworkImageView}


def cleanup_fds(self):
    """ This is a patch of the Supervisor cleanup_fds in ServerOptions.
    The default version is a bit raw and closes all file descriptors of the process, including the PyZmq ones,
    which leads to a low-level crash in select/poll.
    So, given that the issue has never been met with Supvisors and waiting for a better solution in Supervisor
    (a TODO exists in source code), the clean-up is disabled in Supvisors. """


def make_supvisors_rpcinterface(supervisord, **config) -> RPCInterface:
    """ Supervisor entry point. """
    # update Supervisor Fault definition
    expand_faults()
    # update Supervisor http web pages
    update_views()
    # patch the Supervisor ServerOptions.cleanup_fds
    ServerOptions.cleanup_fds = cleanup_fds
    # patch inheritance of supervisor.web.StatusView
    # 2 reasons:
    #    * waiting for Supervisor#1273 to be fixed
    #    * to benefit from the commonalities done in supvisors.ViewHandler
    StatusView.__bases__ = (ViewHandler,)
    # store the Supvisors instance in supervisord instance to ensure persistence
    supervisord.supvisors = Supvisors(supervisord)
    # create and return handler
    return RPCInterface(supervisord.supvisors)
