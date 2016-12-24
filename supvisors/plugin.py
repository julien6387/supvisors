#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from os import path

from supervisor.web import VIEWS
from supervisor.xmlrpc import Faults

from supvisors.initializer import Supvisors
from supvisors.rpcinterface import RPCInterface
from supvisors.viewaddress import AddressView
from supvisors.viewapplication import ApplicationView
from supvisors.viewimage import ProcessImageView, AddressImageView
from supvisors.viewsupvisors import SupvisorsView


# Supvisors related faults
class SupvisorsFaults:
    SUPVISORS_CONF_ERROR, BAD_SUPVISORS_STATE, BAD_ADDRESS, BAD_STRATEGY, BAD_EXTRA_ARGUMENTS = range(5)

FAULTS_OFFSET = 100


# Trick to replace Supervisor main page
def update_views():
    # replace Supervisor main entry
    here = path.abspath(path.dirname(__file__))
    # set main page
    VIEWS['index.html'] =  { 'template': path.join(here, 'ui/index.html'), 'view': SupvisorsView }
    # set address page
    VIEWS['address.html'] =  { 'template': path.join(here, 'ui/address.html'), 'view': AddressView }
    # set application page
    VIEWS['application.html'] =  { 'template': path.join(here, 'ui/application.html'), 'view': ApplicationView }
    # set fake page to export images
    VIEWS['process_stats.png'] =  { 'template': path.join(here, 'ui/empty.html'), 'view': ProcessImageView }
    VIEWS['address_stats.png'] =  { 'template': path.join(here, 'ui/empty.html'), 'view': AddressImageView }

# Supervisor entry point
def make_supvisors_rpcinterface(supervisord, **config):
    # expand supervisord Fault definition (no matter if done several times)
    for (x, y) in SupvisorsFaults.__dict__.items():
        if not x.startswith('__'):
            setattr(Faults, x, y + FAULTS_OFFSET)
    # update http web pages
    update_views()
    # create a new Supvisors instance
    supvisors = Supvisors(supervisord)
    # create and return handler
    return RPCInterface(supvisors)

