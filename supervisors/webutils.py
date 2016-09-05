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

import time

# TODO: list:
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
    elt = root.findmeld('message_mid')
    if message is not None:
        elt.attrib['class'] = gravity
        elt.content(message)
    else:
        elt.replace('')

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

