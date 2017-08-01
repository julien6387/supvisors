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

import errno
import os

from supervisor.options import ServerOptions
from supervisor.web import VIEWS
from supervisor.xmlrpc import Faults

from supvisors.rpcinterface import RPCInterface
from supvisors.viewprocaddress import ProcAddressView
from supvisors.viewhostaddress import HostAddressView
from supvisors.viewapplication import ApplicationView
from supvisors.viewimage import *
from supvisors.viewsupvisors import SupvisorsView


# Supvisors related faults
class SupvisorsFaults:
    SUPVISORS_CONF_ERROR, BAD_SUPVISORS_STATE, BAD_ADDRESS, BAD_STRATEGY, \
    BAD_EXTRA_ARGUMENTS = range(5)

FAULTS_OFFSET = 100

def expand_faults():
    """ Expand supervisord Fault definition. """
    for (x, y) in SupvisorsFaults.__dict__.items():
        if not x.startswith('__'):
            setattr(Faults, x, y + FAULTS_OFFSET)


def update_views():
    """ Trick to replace Supervisor main page. """
    # replace Supervisor main entry
    here = os.path.abspath(os.path.dirname(__file__))
    # set main page
    VIEWS['index.html'] =  {'template': os.path.join(here, 'ui/index.html'),
                            'view': SupvisorsView}
    # set address /processpage
    VIEWS['procaddress.html'] =  {'template': os.path.join(
        here, 'ui/procaddress.html'),
                                  'view': ProcAddressView}
    # set address/host page
    VIEWS['hostaddress.html'] =  {'template': os.path.join(
        here, 'ui/hostaddress.html'),
                                  'view': HostAddressView}
    # set application page
    VIEWS['application.html'] =  {'template': os.path.join(
        here, 'ui/application.html'),
                                  'view': ApplicationView}
    # set fake page to export images
    VIEWS['process_cpu.png'] =  {'template': os.path.join(
        here, 'ui/empty.html'),
                                 'view': ProcessCpuImageView}
    VIEWS['process_mem.png'] =  {'template': os.path.join(
        here, 'ui/empty.html'),
                                 'view': ProcessMemoryImageView}
    VIEWS['address_cpu.png'] =  {'template': os.path.join(
        here, 'ui/empty.html'),
                                 'view': AddressCpuImageView}
    VIEWS['address_mem.png'] =  {'template': os.path.join(
        here, 'ui/empty.html'),
                                 'view': AddressMemoryImageView}
    VIEWS['address_io.png'] =  {'template': os.path.join(
        here, 'ui/empty.html'),
                                'view': AddressNetworkImageView}


def cleanup_fds(self):
    """ This is a patch of the Supervisor cleanup_fds in ServerOptions.
    The default version is a bit rough and closes all file descriptors of
    the process, including the PyZmq ones, which leads to a low-level crash
    in select/poll. """
    pid = os.getpid()
    proc_fd = '/proc/{}/fd'.format(pid)
    zmq_inodes = []
    for fd in os.listdir(proc_fd):
        try:
            inode = os.readlink(proc_fd + '/' + fd)
        except OSError as err:
            if err.errno in (errno.ENOENT, errno.ESRCH, errno.EINVAL):
                continue
            else:
                print('[ERROR] unexpected readlink error: {}'.format(err))
        else:
            # check if the inode is a ZMQ
            if inode.startswith('anon_inode:[') or \
            inode.startswith('socket:['):
                zmq_inodes.append(int(fd))
    # the following is adapted from the original cleanup_fds
    # it just avoids to close the Zmq inodes
    start = 5
    for x in range(start, self.minfds):
        if x not in zmq_inodes:
            try:
                os.close(x)
            except OSError:
                pass


def make_supvisors_rpcinterface(supervisord, **config):
    """ Supervisor entry point. """
    # update Supervisor Fault definition
    expand_faults()
    # update Supervisor http web pages
    update_views()
    # patches the Supervisor ServerOptions.cleanup_fds
    ServerOptions.cleanup_fds = cleanup_fds
    # create and return handler
    return RPCInterface(supervisord)
