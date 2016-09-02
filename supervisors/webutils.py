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

from supervisors.addressmapper import addressMapper
from supervisors.application import applicationStateToString
from supervisors.context import context
from supervisors.remote import remoteStateToString, RemoteStates
from supervisors.statemachine import fsm
from supervisors.types import SupervisorsStates

import time, urllib

# TODO: list:
#   2) tail page
#   3) statistics
#   4) check if deployable for buttons (address / resource) ?
#   6) style for states
#   7) conciliation page

# -----------------------------------------
# common utils

# gravity classes for messages
# use of 'erro' instead of 'error' in order to avoid HTTP error log traces
Info='info'
Warn = 'warn'
Error = 'erro'

def writeNav(root, serverPort, address=None, appli=None):
    # update navigation addresses
    iterator = root.findmeld('address_li_mid').repeat(addressMapper.expectedAddresses)
    for li_element, item in iterator:
        state = context.remotes[item].state
        # set element class
        li_element.attrib['class'] = remoteStateToString(state) + (' active' if address and item == address else '')
        # set hyperlink attributes
        elt = li_element.findmeld('address_a_mid')
        if state == RemoteStates.RUNNING:
            # go to web page located on address, so as to reuse Supervisor StatusView
            elt.attributes(href='http://{}:{}/address.html'.format(item, serverPort))
            elt.attrib['class'] = 'on'
        else:
            elt.attrib['class'] = 'off'
        elt.content(item)
    # update navigation applications
    iterator = root.findmeld('appli_li_mid').repeat(context.applications.keys())
    for li_element, item in iterator:
        state = context.applications[item].state
        # set element class
        li_element.attrib['class'] = applicationStateToString(state) + (' active' if appli and item == appli else '')
        # set hyperlink attributes
        elt = li_element.findmeld('appli_a_mid')
        # go to web page located on Supervisors Master, so as to simplify requests
        if fsm.state == SupervisorsStates.INITIALIZATION:
            elt.attrib['class'] = 'off'
        else:
            elt.attributes(href='http://{}:{}/application.html?appli={}'.format(context.masterAddress, serverPort, urllib.quote(item)))
            elt.attrib['class'] = 'on'
        elt.content(item)

def formatGravityMessage(message):
    if not isinstance(message, tuple):
        # gravity is not set by Supervisor so let's deduce it
        if 'ERROR' in message:
            message = message.replace('ERROR: ', '')
            gravity = Error
        else:
            gravity = Info
        return (gravity, message)
    return message

def printMessage(root, gravity, message):
    # print message as a result of action
    if message is not None:
        elt = root.findmeld('message_mid')
        elt.attrib['class'] = gravity
        elt.content(message)

def infoMessage(msg, address=None):
    return (Info, msg + ' at {}'.format(time.ctime()) + (' on {}'.format(address) if address else ''))

def warnMessage(msg, address=None):
    return (Warn, msg + ' at {}'.format(time.ctime()) + (' on {}'.format(address) if address else ''))

def errorMessage(msg, address=None):
    return (Error, msg + ' at {}'.format(time.ctime()) + (' on {}'.format(address) if address else ''))

def delayedInfo(msg, address=None):
    def onWait():
        return infoMessage(msg, address)
    onWait.delay = 0.05
    return onWait

def delayedWarn(msg, address=None):
    def onWait():
        return warnMessage(msg, address)
    onWait.delay = 0.05
    return onWait

def delayedError(msg, address=None):
    def onWait():
        return errorMessage(msg, address)
    onWait.delay = 0.05
    return onWait

