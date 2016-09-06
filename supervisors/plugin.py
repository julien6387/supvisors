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

# Supervisors related faults
class SupervisorsFaults:
    SUPERVISORS_CONF_ERROR, BAD_SUPERVISORS_STATE, BAD_ADDRESS, BAD_STRATEGY = range(4)

_FAULTS_OFFSET = 100

# Trick to replace Supervisor main page
def updateUiHandler():
    from supervisor.web import VIEWS
    # replace Supervisor main entry
    from os import path
    here = path.abspath(path.dirname(__file__))
    # set main page
    from supervisors.viewsupervisors import SupervisorsView
    VIEWS['index.html'] =  { 'template': path.join(here, 'ui/index.html'), 'view': SupervisorsView }
    # set address page
    from supervisors.viewaddress import AddressView
    VIEWS['address.html'] =  { 'template': path.join(here, 'ui/address.html'), 'view': AddressView }
    # set application page
    from supervisors.viewapplication import ApplicationView
    VIEWS['application.html'] =  { 'template': path.join(here, 'ui/application.html'), 'view': ApplicationView }
    # set fake page to export images
    from supervisors.viewimage import ProcessImageView, AddressImageView
    VIEWS['process_stats.png'] =  { 'template': path.join(here, 'ui/empty.html'), 'view': ProcessImageView }
    VIEWS['address_stats.png'] =  { 'template': path.join(here, 'ui/empty.html'), 'view': AddressImageView }

# Supervisor entry point
def make_supervisors_rpcinterface(supervisord, **config):
    from supervisor.xmlrpc import Faults, RPCError
    # expand supervisord Fault definition (no matter if done several times)
    for (x, y) in SupervisorsFaults.__dict__.items():
        if not x.startswith('__'):
            setattr(Faults, x, y + _FAULTS_OFFSET)
    # configure supervisor info source
    from supervisors.infosource import infoSource
    infoSource.setSupervisorInstance(supervisord)
    # get options from config file
    from supervisors.options import options
    options.realize()
    # set addresses and check local address
    from supervisors.addressmapper import addressMapper
    addressMapper.setAddresses(options.addressList)
    if not addressMapper.localAddress:
        raise RPCError(Faults.SUPERVISORS_CONF_ERROR, 'local host unexpected in address list: {}'.format(options.addressList))
    from supervisors.context import context
    context.restart()
    from supervisors.statemachine import fsm
    fsm.restart()
    # check parsing
    from supervisors.parser import parser
    try:
        parser.setFilename(options.deploymentFile)
    except:
        raise RPCError(Faults.SUPERVISORS_CONF_ERROR, 'cannot parse deployment file: {}'.format(options.deploymentFile))
    # update http web pages
    updateUiHandler()
    # create and return handler
    from supervisors.rpcinterface import RPCInterface
    return RPCInterface()
