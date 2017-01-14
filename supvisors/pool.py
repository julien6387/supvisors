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

import json
import logging

from multiprocessing import Pool
from multiprocessing import util # for logs

from supvisors.rpcrequests import getRPCInterface
from supvisors.ttypes import AddressStates
from supvisors.utils import SUPVISORS_AUTH, SUPVISORS_INFO


def set_util_logger():
    """ Very simple logger to help debug Pool. """
    hand = logging.StreamHandler()
    hand.setFormatter(logging.Formatter('%(message)s'))
    util.get_logger().addHandler(hand)
    util.get_logger().setLevel(util.DEBUG)

# for DEBUG
# set_util_logger()


def async_check_address(address_name, env):
    """ Check isolation and get all process info asynchronously. """
    try:
        local_proxy = getRPCInterface("localhost", env)
        remote_proxy = getRPCInterface(address_name, env)
        # check authorization
        status = remote_proxy.supvisors.get_address_info(address_name)
        authorized = status['statecode'] not in [AddressStates.ISOLATING, AddressStates.ISOLATED]
        # get process info if authorized
        if authorized:
            all_info = remote_proxy.supervisor.getAllProcessInfo()
            local_proxy.supervisor.sendRemoteCommEvent(SUPVISORS_INFO, json.dumps((address_name, all_info)))
        # inform local Supvisors that authorization is available
        local_proxy.supervisor.sendRemoteCommEvent(SUPVISORS_AUTH, 'address_name:{} authorized:{}'.format(address_name, authorized))
    except:
        pass

def async_start_process(address_name, namespec, extra_args, env):
    """ Start process asynchronously. """
    try:
        proxy = getRPCInterface(address_name, env)
        proxy.supvisors.start_args(namespec, extra_args, False)
    except:
        pass

def async_stop_process(address_name, namespec, env):
    """ Stop process asynchronously. """
    try:
        proxy = getRPCInterface(address_name, env)
        proxy.supervisor.stopProcess(namespec, False)
    except:
        pass

def async_restart(address_name, env):
    """ Restart a Supervisor instance asynchronously. """
    try:
        proxy = getRPCInterface(address_name, env)
        proxy.supervisor.restart()
    except:
        pass

def async_shutdown(address_name, env):
    """ Stop process asynchronously. """
    try:
        proxy = getRPCInterface(address_name, env)
        proxy.supervisor.shutdown()
    except:
        pass

class SupvisorsPool:
    """ Use a pool of one process to perform asynchronous requests.
    
    Supvisors works in the context of the main thread of the supervisor daemon.
    It consequently blocks any incoming XML-RPC as long as its job is in progress.
    The problem is that Supvisors sometimes uses XML-RPC towards another supervisor daemon running elsewhere.
    If the Supvisors of the other instance is doing the same at the same time, both are blocking themselves.

    That's why the XML-RPC performed by Supvisors are performed asynchronously.

    Attributes are:
        - env: the environment-like Supervisor variables,
        - pool: the pool of processes that handles the asynchronous calls.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.logger = supvisors.logger
        self.env = supvisors.info_source.get_env()
        # create the pool worker
        self.pool = Pool(1)

    def close(self):
        """ Close the pool gracefully and join it. """
        self.logger.info('closing pool')
        try:
            self.pool.close()
        except (EOFError, IOError) as e:
            # happened a few times but did not found anything to solve this
            print '### ERROR when closing Pool:', e
        # wait for all jobs to terminate
        self.pool.join()
        self.logger.info('pool closed')

    def async_check_address(self, address_name):
        """ Check isolation and get all process information from address.
        Use an asynchronous remote communication event to inform that information is available. """
        return self.pool.apply_async(async_check_address, (address_name, self.env))

    def async_start_process(self, address_name, namespec, extra_args):
        """ Schedule an asynchronous call to start a process. """
        return self.pool.apply_async(async_start_process, (address_name, namespec, extra_args, self.env))

    def async_stop_process(self, address_name, namespec):
        """ Schedule an asynchronous call to stop a process. """
        return self.pool.apply_async(async_stop_process, (address_name, namespec, self.env))

    def async_restart(self, address_name):
        """ Schedule an asynchronous call to restart a Supervisor instance. """
        return self.pool.apply_async(async_restart, (address_name, self.env))

    def async_shutdown(self, address_name):
        """ Schedule an asynchronous call to restart a Supervisor instance. """
        return self.pool.apply_async(async_shutdown, (address_name, self.env))
