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

import logging

from multiprocessing import Manager, Pool
from multiprocessing import util # for logs

from supvisors.rpcrequests import getRPCInterface
from supvisors.utils import SUPVISORS_EVENT, SUPVISORS_INFO, SUPVISORS_TASK


def set_util_logger():
    """ Very simple logger to help debug Pool. """
    hand = logging.StreamHandler()
    hand.setFormatter(logging.Formatter('%(message)s'))
    util.get_logger().addHandler(hand)
    util.get_logger().setLevel(util.DEBUG)

# for DEBUG
# set_util_logger()


def set_async_proxy(*args):
    """ Trick to assign a persistent supervisor proxy to the pool. """
    SupvisorsPool.proxy = getRPCInterface("localhost", args[0])

def async_remote_comm_event(type_event):
    """ Send a remote communication event to the local Supervisor daemon. """
    try:
        SupvisorsPool.proxy.supervisor.sendRemoteCommEvent(type_event, '')
    except:
        pass

def async_get_all_process_info(address_name, env, queue):
    """ Get all process info asynchronously. """
    try:
        proxy = getRPCInterface(address_name, env)
        queue.put((address_name, proxy.supervisor.getAllProcessInfo()))
        async_remote_comm_event(SUPVISORS_INFO)
    except:
        pass


class SupvisorsPool:
    """ Use a pool of one process to perform asynchronous requests.
    
    Supvisors works in the context of the main thread of the supervisor daemon.
    It consequently blocks any incoming XML-RPC as long as its job is in progress.
    The problem is that Supvisors sometimes uses XML-RPC towards another supervisor daemon running elsewhere.
    If the Supvisors of the other instance is doing the same at the same time, both are blocking themselves.

    That's why the XML-RPC performed by Supvisors are performed asynchronously when possible.

    Attributes are:
    - env: the environment-like Supervisor variables,
    - pool: the pool of processes that handles the asynchronous calls,
    - manager: the manager that delivers shared context,
    - info_queue: the queue for process information.

    The proxy attribute is used to persist the proxy for XML-RPC towards Supervisor.
    """

    proxy = None

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.env = supvisors.info_source.get_env()
        self.pool = Pool(1, set_async_proxy, (self.env, ))
        self.manager = Manager()
        self.info_queue = self.manager.Queue()

    def close(self):
        """ Close the pool gracefully and join it. """
        self.info_queue = None
        self.manager.shutdown()
        self.pool.terminate()
        # WARN: do NOT join the pool
        # XML-RPC are blocking. If one is triggered when supervisor is closing, the join will block forever.
        # supervisor cannot process the XML-RPC as long as its current action is in progress, i.e. this join.
        # the Pool terminate does not abort a task in progress and the join cannot be completed as long as
        # the task in progress is not completed.
        # self.pool.join()

    def async_event(self):
        """ Use an asynchronous remote communication event to inform
        that an event is available. """
        self.pool.apply_async(async_remote_comm_event, (SUPVISORS_EVENT, ))

    def async_task(self):
        """ Use an asynchronous remote communication event to inform
        that a periodic task can be performed. """
        self.pool.apply_async(async_remote_comm_event, (SUPVISORS_TASK, ))

    def async_process_info(self, address_name):
        """ Get all process inofrmation from address and use an asynchronous remote
        communication event to inform that information is available. """
        self.pool.apply_async(async_get_all_process_info, (address_name, self.env, self.info_queue))
