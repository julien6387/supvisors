#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import re
from unittest.mock import call

from supervisor.loggers import BoundIO, LevelsByName, LogRecord, StreamHandler
from supervisor.web import OKView, TailView

from supvisors.plugin import *
from .base import DummySupervisor


def test_expand_faults():
    """ Test the expand_faults function. """
    expand_faults()
    assert SupvisorsFaults.SUPVISORS_CONF_ERROR.value == Faults.SUPVISORS_CONF_ERROR
    assert SupvisorsFaults.BAD_SUPVISORS_STATE.value == Faults.BAD_SUPVISORS_STATE
    assert SupvisorsFaults.NOT_MANAGED.value == Faults.NOT_MANAGED
    assert SupvisorsFaults.DISABLED.value == Faults.DISABLED


def test_patch_logger(supvisors):
    """ Test the patch_logger function. """
    # check initial context
    assert not hasattr(Handler, '_emit')
    ref_emit = Handler.emit
    # check monkeypatch
    patch_logger()
    assert Handler._emit is ref_emit
    assert Handler.emit is not ref_emit
    # check again monkeypatch to ensure that Supvisors patches do not override renamed Supervisor functions
    patch_logger()
    assert Handler._emit is ref_emit
    assert Handler.emit is not ref_emit
    # test log emission
    io = BoundIO(1 << 10)
    handler = StreamHandler(io)
    handler.emit(LogRecord(LevelsByName.INFO, 'hello'))
    assert io.getvalue() == b'hello'


def test_patch_591():
    """ Test the patch_591 function. """
    # check initial context
    assert not hasattr(SupervisorNamespaceRPCInterface, '_startProcess')
    assert not hasattr(Subprocess, '_spawn')
    ref_start_process = SupervisorNamespaceRPCInterface.startProcess
    ref_spawn = Subprocess.spawn
    # check monkeypatch
    patch_591()
    assert SupervisorNamespaceRPCInterface._startProcess is ref_start_process
    assert Subprocess._spawn is ref_spawn
    assert SupervisorNamespaceRPCInterface.startProcess is startProcess
    assert Subprocess.spawn is spawn
    # check again monkeypatch to ensure that Supvisors patches do not override renamed Supervisor functions
    patch_591()
    assert SupervisorNamespaceRPCInterface._startProcess is ref_start_process
    assert Subprocess._spawn is ref_spawn
    assert SupervisorNamespaceRPCInterface.startProcess is startProcess
    assert Subprocess.spawn is spawn


def test_update_views():
    """ Test the update_views function. """
    # update Supervisor views
    update_views()
    # check Supvisors views
    view = VIEWS['index.html']
    assert re.search(r'supvisors/ui/index\.html$', view['template'])
    assert view['view'] == SupvisorsView
    view = VIEWS['ok.html']
    assert view['template'] is None
    assert OKView == view['view']
    view = VIEWS['tail.html']
    assert view['template'] == 'ui/tail.html'
    assert TailView == view['view']
    view = VIEWS['application.html']
    assert re.search(r'supvisors/ui/application\.html$', view['template'])
    assert ApplicationView == view['view']
    view = VIEWS['host_instance.html']
    assert re.search(r'supvisors/ui/host_instance\.html$', view['template'])
    assert HostInstanceView == view['view']
    view = VIEWS['proc_instance.html']
    assert re.search(r'supvisors/ui/proc_instance\.html$', view['template'])
    assert ProcInstanceView == view['view']
    view = VIEWS['host_mem.png']
    assert view['template'] is None
    assert HostMemoryImageView == view['view']
    view = VIEWS['process_mem.png']
    assert view['template'] is None
    assert ProcessMemoryImageView == view['view']
    view = VIEWS['host_cpu.png']
    assert view['template'] is None
    assert HostCpuImageView == view['view']
    view = VIEWS['process_cpu.png']
    assert view['template'] is None
    assert ProcessCpuImageView == view['view']
    view = VIEWS['host_io.png']
    assert view['template'] is None
    assert HostNetworkImageView == view['view']


def test_make_rpc(mocker):
    """ Test the make_supvisors_rpcinterface function. """
    mocked_expand = mocker.patch('supvisors.plugin.expand_faults')
    mocked_logger = mocker.patch('supvisors.plugin.patch_logger')
    mocked_591 = mocker.patch('supvisors.plugin.patch_591')
    mocked_views = mocker.patch('supvisors.plugin.update_views')
    mocker.patch('supvisors.plugin.Supvisors', return_value='a Supvisors instance')
    mocked_rpc = mocker.patch('supvisors.plugin.RPCInterface')
    supervisord = DummySupervisor()
    # save cleanup_fds function
    cleanup = ServerOptions.cleanup_fds
    # create the RPC interface
    make_supvisors_rpcinterface(supervisord)
    # test the calls to previous functions
    assert supervisord.supvisors == 'a Supvisors instance'
    assert mocked_expand.call_args_list == [call()]
    assert mocked_rpc.call_args_list == [call(supervisord.supvisors)]
    assert mocked_logger.call_args_list == [call()]
    assert mocked_591.call_args_list == [call()]
    assert mocked_views.call_args_list == [call()]
    # test monkeypatch of Supervisor cleanup_fds
    assert ServerOptions.cleanup_fds is not cleanup
