#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2018 Julien LE CLEACH
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
from unittest.mock import call, Mock

import pytest

from supvisors.web.viewcontext import *
from .base import DummyHttpContext

url_attr_template = r'(.+=.+)'


@pytest.fixture
def http_context(supvisors):
    """ Fixture for Dummy HTTP Context. """
    http_context = DummyHttpContext('')
    http_context.supervisord.supvisors = supvisors
    return http_context


@pytest.fixture
def ctx(http_context):
    """ Fixture for the instance to test. """
    return ViewContext(http_context)


def test_init(http_context, ctx):
    """ Test the values set at ViewContext construction. """
    assert ctx.http_context is http_context
    assert ctx.supvisors is http_context.supervisord.supvisors
    assert ctx.local_identifier == ctx.supvisors.mapper.local_identifier
    assert ctx.parameters == {'ident': '10.0.0.4', 'namespec': None, 'period': 5,
                              'appliname': None, 'processname': None, 'cpuid': 0,
                              'intfname': None, 'auto': False, 'strategy': 'CONFIG', 'shex': ''}
    # errors must be set due to dummy values
    assert isinstance(ctx.store_message, tuple)
    assert len(ctx.store_message) == 2
    assert ctx.store_message[0] == 'erro'
    assert not ctx.redirect


def test_get_action(ctx):
    """ Test the ViewContext.get_action method. """
    assert ctx.get_action() == 'test'


def test_get_node_name(ctx):
    """ Test the ViewContext.get_identifier method. """
    assert ctx.get_identifier() == '10.0.0.4'


def test_get_message(ctx):
    """ Test the ViewContext.get_message method. """
    assert ctx.get_message() == 'hi chaps'


def test_get_gravity(ctx):
    """ Test the ViewContext.get_gravity method. """
    assert ctx.get_gravity() == 'none'


def test_url_parameters(ctx):
    """ Test the ViewContext.url_parameters method. """
    # test default
    assert ctx.url_parameters(False) == 'ident=10.0.0.4&period=5.0&strategy=CONFIG'
    assert ctx.url_parameters(True) == 'ident=10.0.0.4&period=5.0&strategy=CONFIG'
    # update internal parameters
    ctx.parameters.update({'processname': 'dummy_proc', 'namespec': 'dummy_ns', 'ident': '10.0.0.1', 'cpuid': 3,
                           'intfname': 'eth0', 'appliname': 'dummy_appli', 'period': 8, 'strategy': 'CONFIG',
                           'shex': '10101'})
    # test without additional parameters
    # don't reset shex
    url = ctx.url_parameters(False)
    # result depends on dict contents so ordering is unreliable
    regexp = r'&'.join([url_attr_template for _ in range(9)])
    matches = re.match(regexp, url)
    assert matches is not None
    expected = sorted(('processname=dummy_proc', 'namespec=dummy_ns', 'ident=10.0.0.1', 'cpuid=3', 'intfname=eth0',
                       'appliname=dummy_appli', 'period=8', 'strategy=CONFIG', 'shex=10101'))
    assert sorted(matches.groups()) == expected
    # reset shex
    url = ctx.url_parameters(True)
    # result depends on dict contents so ordering is unreliable
    regexp = r'&'.join([url_attr_template for _ in range(8)])
    matches = re.match(regexp, url)
    assert matches is not None
    expected = sorted(('processname=dummy_proc', 'namespec=dummy_ns', 'ident=10.0.0.1', 'cpuid=3', 'intfname=eth0',
                       'appliname=dummy_appli', 'period=8', 'strategy=CONFIG'))
    assert sorted(matches.groups()) == expected
    # test with additional parameters
    # don't reset shex
    url = ctx.url_parameters(False, **{'ident': '127.0.0.1', 'intfname': 'lo', 'shex': 'args'})
    regexp = r'&'.join([url_attr_template for _ in range(9)])
    matches = re.match(regexp, url)
    assert matches is not None
    expected = sorted(('processname=dummy_proc', 'namespec=dummy_ns', 'ident=127.0.0.1', 'cpuid=3', 'intfname=lo',
                       'shex=args', 'appliname=dummy_appli', 'period=8', 'strategy=CONFIG'))
    assert sorted(matches.groups()) == expected
    # test with additional parameters
    # reset shex
    url = ctx.url_parameters(True, **{'ident': '127.0.0.1', 'intfname': 'lo', 'shex': 'args'})
    regexp = r'&'.join([url_attr_template for _ in range(8)])
    matches = re.match(regexp, url)
    assert matches is not None
    expected = sorted(('processname=dummy_proc', 'namespec=dummy_ns', 'ident=127.0.0.1', 'cpuid=3', 'intfname=lo',
                       'appliname=dummy_appli', 'period=8', 'strategy=CONFIG'))
    assert sorted(matches.groups()) == expected


def test_cpu_id_to_string():
    """ Test the ViewContext.cpu_id_to_string method. """
    for idx in range(1, 10):
        assert ViewContext.cpu_id_to_string(idx) == str(idx - 1)
    assert ViewContext.cpu_id_to_string(0) == 'all'
    assert ViewContext.cpu_id_to_string(-5) == 'all'


def test_update_string(ctx):
    """ Test the ViewContext._update_string method. """
    # keep a copy of parameters
    ref_parameters = ctx.parameters.copy()
    # test with unknown parameter and no default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_string('dummy', [])
    ref_parameters.update({'dummy': None})
    assert ctx.parameters == ref_parameters
    # test with unknown parameter and default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_string('dummy', [], 'hello')
    ref_parameters.update({'dummy': 'hello'})
    assert ctx.parameters == ref_parameters
    # test with known parameter, no default value and value out of list
    assert 'action' in ctx.http_context.form
    ctx._update_string('action', [])
    ref_parameters.update({'action': None})
    assert ctx.parameters == ref_parameters
    # test with known parameter, default value and value out of list
    assert 'action' in ctx.http_context.form
    ctx._update_string('action', [], 'do it')
    ref_parameters.update({'action': 'do it'})
    assert ctx.parameters == ref_parameters
    # test with known parameter and value in list
    assert 'action' in ctx.http_context.form
    ctx._update_string('action', ['try', 'do it', 'test'])
    ref_parameters.update({'action': 'test'})
    assert ctx.parameters == ref_parameters


def test_update_integer(ctx):
    """ Test the ViewContext._update_integer method. """
    # keep a copy of parameters
    ref_parameters = ctx.parameters.copy()
    # test with unknown parameter and no default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_integer('dummy', [])
    ref_parameters.update({'dummy': 0})
    assert ctx.parameters == ref_parameters
    # test with unknown parameter and default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_integer('dummy', [], 'hello')
    ref_parameters.update({'dummy': 'hello'})
    assert ctx.parameters == ref_parameters
    # test with known parameter, not integer and no default value
    assert 'action' in ctx.http_context.form
    ctx._update_integer('action', [])
    ref_parameters.update({'action': 0})
    # test with known parameter, not integer and default value
    assert 'action' in ctx.http_context.form
    ctx._update_integer('action', [], 5)
    ref_parameters.update({'action': 5})
    # test with known parameter, integer, no default value and value out of list
    assert 'SERVER_PORT' in ctx.http_context.form
    ctx._update_integer('SERVER_PORT', [])
    ref_parameters.update({'SERVER_PORT': 0})
    assert ctx.parameters == ref_parameters
    # test with known parameter, integer, default value and value out of list
    assert 'SERVER_PORT' in ctx.http_context.form
    ctx._update_integer('SERVER_PORT', [], 1234)
    ref_parameters.update({'SERVER_PORT': 1234})
    assert ctx.parameters == ref_parameters
    # test with known parameter, integer and value in list
    assert 'SERVER_PORT' in ctx.http_context.form
    ctx._update_integer('SERVER_PORT', [12, 7777, 654])
    ref_parameters.update({'SERVER_PORT': 7777})
    assert ctx.parameters == ref_parameters


def test_update_float(ctx):
    """ Test the ViewContext._update_float method. """
    # keep a copy of parameters
    ref_parameters = ctx.parameters.copy()
    # test with unknown parameter and no default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_float('dummy', [])
    ref_parameters.update({'dummy': 0})
    assert ctx.parameters == ref_parameters
    # test with unknown parameter and default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_float('dummy', [], 'hello')
    ref_parameters.update({'dummy': 'hello'})
    assert ctx.parameters == ref_parameters
    # test with known parameter, not float and no default value
    assert 'action' in ctx.http_context.form
    ctx._update_float('action', [])
    ref_parameters.update({'action': 0.0})
    # test with known parameter, not float and default value
    assert 'action' in ctx.http_context.form
    ctx._update_float('action', [], 5.0)
    ref_parameters.update({'action': 5.0})
    # test with known parameter, float, no default value and value out of list
    assert 'period' in ctx.http_context.form
    ctx._update_float('period', [])
    ref_parameters.update({'period': 0.0})
    assert ctx.parameters == ref_parameters
    # test with known parameter, float, default value and value out of list
    assert 'period' in ctx.http_context.form
    ctx._update_float('period', [], 12.3)
    ref_parameters.update({'period': 12.3})
    assert ctx.parameters == ref_parameters
    # test with known parameter, float and value in list
    assert 'period' in ctx.http_context.form
    ctx._update_float('period', [5.1, 15.0, 60.0])
    ref_parameters.update({'period': 5.1})
    assert ctx.parameters == ref_parameters


def test_update_boolean(ctx):
    """ Test the ViewContext._update_boolean method. """
    # keep a copy of parameters
    ref_parameters = ctx.parameters.copy()
    # test with unknown parameter and no default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_boolean('dummy')
    ref_parameters.update({'dummy': False})
    assert ctx.parameters == ref_parameters
    # test with unknown parameter and default value
    assert 'dummy' not in ctx.http_context.form
    ctx._update_boolean('dummy', True)
    ref_parameters.update({'dummy': True})
    assert ctx.parameters == ref_parameters
    # test with known parameter, no default value and unexpected value
    ctx.http_context.form['auto'] = 'unexpected value'
    ctx._update_boolean('auto')
    ref_parameters.update({'auto': False})
    assert ctx.parameters == ref_parameters
    # test with known parameter, default value and unexpected value
    ctx._update_boolean('auto', True)
    ref_parameters.update({'auto': True})
    assert ctx.parameters == ref_parameters
    # test with known parameter and expected value
    ctx.http_context.form['auto'] = '1'
    ctx._update_boolean('auto')
    ref_parameters.update({'auto': True})
    assert ctx.parameters == ref_parameters


def test_update_period(mocker, ctx):
    """ Test the ViewContext.update_period method. """
    mocked_update = mocker.patch('supvisors.web.viewcontext.ViewContext._update_float')
    # test method with statistics enabled
    ctx.update_period()
    assert mocked_update.call_args_list == [call(PERIOD, ctx.supvisors.options.stats_periods,
                                                 ctx.supvisors.options.stats_periods[0])]
    mocker.resetall()
    # test method with statistics disabled
    ctx.supvisors.options.stats_periods = []
    with pytest.raises(StopIteration):
        ctx.update_period()
    assert not mocked_update.called


def test_update_identifier(ctx):
    """ Test the ViewContext.update_identifier method. """
    # reset parameter because called in constructor
    del ctx.parameters[IDENTIFIER]
    # test call with valid value
    ctx.update_identifier()
    assert ctx.parameters[IDENTIFIER] == '10.0.0.4'
    # reset parameter
    del ctx.parameters[IDENTIFIER]
    # test call with invalid value
    ctx.http_context.form[IDENTIFIER] = '192.168.1.1'
    ctx.update_identifier()
    assert ctx.parameters[IDENTIFIER] == ctx.local_identifier


def test_update_auto_refresh(ctx):
    """ Test the ViewContext.update_auto_refresh method. """
    # reset parameter because called in constructor
    del ctx.parameters[AUTO]
    # test call with default valid value
    ctx.update_auto_refresh()
    assert not ctx.parameters[AUTO]
    # reset parameter
    del ctx.parameters[AUTO]
    # test call with other valid value
    ctx.http_context.form[AUTO] = 't'
    ctx.update_auto_refresh()
    assert ctx.parameters[AUTO]
    # reset parameter
    del ctx.parameters[AUTO]
    # test call with invalid value
    ctx.http_context.form[AUTO] = 'not a boolean'
    ctx.update_auto_refresh()
    assert not ctx.parameters[AUTO]


def test_update_application_name(ctx):
    """ Test the ViewContext.update_application_name method. """
    # reset parameter because called in constructor
    del ctx.parameters[APPLI]
    # test call with valid value
    ctx.supvisors.context.applications = {'abc': [], 'dummy_appli': []}
    ctx.update_application_name()
    # cannot rely on ordering for second parameter because of dict need to split checking
    assert ctx.parameters[APPLI] == 'dummy_appli'
    # reset parameter
    del ctx.parameters[APPLI]
    # test call with invalid value
    ctx.http_context.form[APPLI] = 'any_appli'
    ctx.update_application_name()
    assert ctx.parameters[APPLI] is None


def test_update_process_name(mocker, ctx):
    """ Test the ViewContext.update_process_name method. """
    ctx.parameters[IDENTIFIER] = ctx.local_identifier
    node = ctx.supvisors.context.instances[ctx.local_identifier]
    mocker.patch.object(node, 'running_processes', return_value=[])
    # reset parameter because called in constructor
    del ctx.parameters[PROCESS]
    # test call in case of node stats are not found
    ctx.update_process_name()
    assert ctx.parameters[PROCESS] is None
    # reset parameter
    del ctx.parameters[PROCESS]
    # test call when address stats are found and process in list
    node.running_processes.return_value = [Mock(namespec='abc'), Mock(namespec='dummy_proc')]
    ctx.update_process_name()
    assert ctx.parameters[PROCESS] == 'dummy_proc'
    # reset parameter
    del ctx.parameters[PROCESS]
    # test call when address stats are found and process not in list
    ctx.http_context.form[PROCESS] = 'any_proc'
    ctx.update_process_name()
    assert ctx.parameters[PROCESS] is None


def test_update_namespec(mocker, ctx):
    """ Test the ViewContext.update_namespec method. """
    # reset parameter because called in constructor
    del ctx.parameters[NAMESPEC]
    # test call with no value
    ctx.update_namespec()
    assert ctx.parameters[NAMESPEC] is None
    # test call with invalid value
    ctx.http_context.form[NAMESPEC] = 'any_proc'
    ctx.update_namespec()
    assert ctx.parameters[NAMESPEC] is None
    # test call with valid parameter
    mocker.patch.object(ctx.http_context.supervisord.supvisors.context, 'is_namespec', return_value=True)
    ctx.update_namespec()
    assert ctx.parameters[NAMESPEC] == 'any_proc'


def test_update_cpu_id(mocker, ctx):
    """ Test the ViewContext.update_cpu_id method. """
    mocker.patch('supvisors.web.viewcontext.ViewContext.get_nb_cores', return_value=2)
    mocked_update = mocker.patch('supvisors.web.viewcontext.ViewContext._update_integer')
    # test call
    ctx.update_cpu_id()
    assert mocked_update.call_args_list == [call(CPU, [0, 1, 2])]


def test_update_interface_name(mocker, ctx):
    """ Test the ViewContext.update_interface_name method. """
    mocked_stats = mocker.patch('supvisors.web.viewcontext.ViewContext.get_instance_stats', return_value=None)
    ctx = ViewContext(ctx.http_context)
    # reset parameter because called in constructor
    del ctx.parameters[INTF]
    # test call in case of address stats are not found
    ctx.update_interface_name()
    assert ctx.parameters[INTF] is None
    # reset parameter
    del ctx.parameters[INTF]
    # test call when address stats are found and process in list
    mocked_stats.return_value = Mock(io={'lo': None})
    ctx.update_interface_name()
    assert ctx.parameters[INTF] == 'lo'
    # reset parameter
    del ctx.parameters[INTF]
    # test call when address stats are found and process not in list
    mocked_stats.return_value = Mock(io={'lo': None, 'eth0': None})
    ctx.update_interface_name()
    assert ctx.parameters[INTF] == 'eth0'


def test_format_url(ctx):
    """ Test the ViewContext.format_url method. """
    # test without node and arguments
    assert ctx.format_url(None, 'index.html') == 'index.html?ident=10.0.0.4&period=5.0&strategy=CONFIG'
    # test with local node and arguments
    local_instance = ctx.supvisors.mapper.local_instance
    base_address = f'http://{local_instance.host_id}:65000/index.html?'
    url = ctx.format_url(ctx.local_identifier, 'index.html',
                         **{'period': 10, 'appliname': 'dummy_appli', 'shex': 'args'})
    expected = 'appliname=dummy_appli&ident=10.0.0.4&period=10&shex=args&strategy=CONFIG'
    assert url == base_address + expected
    # test with remote node and arguments (shex expected to be removed)
    url = ctx.format_url('10.0.0.1', 'index.html',
                         **{'period': 10, 'appliname': 'dummy_appli', 'shex': 'args'})
    base_address = 'http://10.0.0.1:65000/index.html?'
    expected = 'appliname=dummy_appli&ident=10.0.0.4&period=10&strategy=CONFIG'
    assert url == base_address + expected


def test_fire_message(ctx):
    """ Test the ViewContext.fire_message method. """
    ctx.store_message = ('warning', 'not as expected')
    ctx.fire_message()
    # result depends on dict contents so ordering is unreliable
    url = ctx.http_context.response['headers']['Location']
    base_address = 'http://10.0.0.1:7777/index.html?'
    expected = 'gravity=warning&ident=10.0.0.4&message=not%20as%20expected&period=5.0&strategy=CONFIG'
    assert url == base_address + expected


def test_get_nb_cores(ctx):
    """ Test the ViewContext.get_nb_cores method. """
    # test default
    assert ctx.get_nb_cores() == 0
    # mock the structure
    stats = ctx.http_context.supervisord.supvisors.host_compiler
    stats.nb_cores[ctx.local_identifier] = 4
    # test new call
    assert ctx.get_nb_cores() == 4
    # test with unknown address
    assert ctx.get_nb_cores('10.0.0.1') == 0
    # test with known address
    stats.nb_cores['10.0.0.1'] = 8
    assert ctx.get_nb_cores('10.0.0.1') == 8


def test_get_node_stats(supvisors, ctx):
    """ Test the ViewContext.get_instance_stats method. """
    # test with default address
    instance_stats = ctx.get_instance_stats()
    assert instance_stats.identifier == supvisors.mapper.local_identifier
    assert instance_stats.period == 5.0
    # test with unknown identifier
    assert ctx.get_instance_stats('10.0.0.0') is None
    # test with known address parameter and existing period
    instance_stats = ctx.get_instance_stats('10.0.0.1')
    assert instance_stats.identifier == '10.0.0.1'
    assert instance_stats.period == 5.0
    # update with unknown period
    ctx.parameters[PERIOD] = 8
    assert ctx.get_instance_stats('10.0.0.1') is None


def test_get_process_stats(mocker, supvisors, ctx):
    """ Test the ViewContext.get_process_stats method. """
    mocked_core = mocker.patch('supvisors.web.viewcontext.ViewContext.get_nb_cores', return_value=4)
    # test no result as no data stored
    assert ctx.get_process_stats('dummy_proc') == (4, None)
    mocked_core.reset_mock()
    # fill some internal structures
    mocked_stats = mocker.patch.object(supvisors.process_compiler, 'get_stats', return_value='mock stats')
    assert ctx.get_process_stats('dummy_proc', '10.0.0.1') == (4, 'mock stats')
    assert mocked_core.call_args_list == [call('10.0.0.1')]
    assert mocked_stats.call_args_list == [call('dummy_proc', '10.0.0.1', 5.0)]


def test_get_process_status(mocker, ctx):
    """ Test the ViewContext.get_process_status method. """
    # test with empty context and nothing in http form
    mocked_get = mocker.patch.object(ctx.supvisors.context, 'get_process', side_effect=KeyError)
    assert ctx.get_process_status() is None
    assert not mocked_get.called
    assert ctx.get_process_status('abc') is None
    assert mocked_get.call_args_list == [call('abc')]
    mocked_get.reset_mock()
    # test with empty context and namespec in http form
    ctx.parameters[NAMESPEC] = 'abc'
    assert ctx.get_process_status() is None
    assert mocked_get.call_args_list == [call('abc')]
    mocked_get.reset_mock()
    assert ctx.get_process_status('dummy_proc') is None
    assert mocked_get.call_args_list == [call('dummy_proc')]
    mocked_get.reset_mock()
    # test with context and namespec in http form
    mocked_get.side_effect = None
    mocked_get.return_value = 'dummy_proc'
    assert ctx.get_process_status() == 'dummy_proc'
    assert ctx.get_process_status('abc') == 'dummy_proc'
    # test with context and nothing in http form
    ctx.parameters[NAMESPEC] = None
    assert ctx.get_process_status() is None
    assert ctx.get_process_status('dummy_proc') == 'dummy_proc'


def test_get_default_shex(ctx):
    """ Test the ViewContext.get_default_shex method. """
    ctx.supvisors.context.applications = {f'appli_{x}': Mock() for x in range(15)}
    assert ctx.get_default_shex(True).hex() == 'ffff'
    assert ctx.get_default_shex(False).hex() == '0000'


def test_update_shrink_expand(ctx):
    """ Test the ViewContext.update_shrink_expand method. """
    # check default
    assert ctx.parameters[SHRINK_EXPAND] == ''
    assert SHRINK_EXPAND not in ctx.http_context.form
    # test with applications in the context
    ctx.supvisors.context.applications = {'abc': [], 'def': [], 'ghi': []}
    # test with unknown parameter and no default value
    ctx.update_shrink_expand()
    assert ctx.parameters[SHRINK_EXPAND] == 'ff'
    # add unexpected value in form (there should be only even number of hexadecimal chars)
    ctx.http_context.form[SHRINK_EXPAND] = '12A'
    ctx.update_shrink_expand()
    assert ctx.parameters[SHRINK_EXPAND] == 'ff'
    ctx.http_context.form[SHRINK_EXPAND] = '12AG'
    ctx.update_shrink_expand()
    assert ctx.parameters[SHRINK_EXPAND] == 'ff'
    # update form with unexpected value (string length should be equal to the number of applications)
    ctx.http_context.form[SHRINK_EXPAND] = '0101'
    ctx.update_shrink_expand()
    assert ctx.parameters[SHRINK_EXPAND] == 'ff'
    # update form with valid value
    ctx.http_context.form[SHRINK_EXPAND] = '9a'
    ctx.update_shrink_expand()
    assert ctx.parameters[SHRINK_EXPAND] == '9a'


def test_get_application_shex(ctx):
    """ Test the ViewContext.get_application_shex method. """
    # patch the context
    ctx.supvisors.context.applications = {'abc': [], 'def': [], 'ghi': []}
    # only 'def' is visible
    ba = bytearray([0xff])
    set_bit(ba, 0, 0)
    set_bit(ba, 2, 0)
    assert ba.hex() == 'fa'
    ctx.parameters[SHRINK_EXPAND] = 'fa'
    # test calls and inversion
    assert ctx.get_application_shex('abc') == (False, 'fb')
    assert get_bit(ba.fromhex('fb'), 0)
    assert get_bit(ba.fromhex('fb'), 1)
    assert not get_bit(ba.fromhex('fb'), 2)
    assert ctx.get_application_shex('def') == (True, 'f8')
    assert not get_bit(ba.fromhex('f8'), 0)
    assert not get_bit(ba.fromhex('f8'), 1)
    assert not get_bit(ba.fromhex('f8'), 2)
    assert ctx.get_application_shex('ghi') == (False, 'fe')
    assert not get_bit(ba.fromhex('fe'), 0)
    assert get_bit(ba.fromhex('fe'), 1)
    assert get_bit(ba.fromhex('fe'), 2)
