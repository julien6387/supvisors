#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2020 Julien LE CLEACH
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

import pytest

from supervisor.web import StatusView

from unittest.mock import call, Mock

from supvisors.viewcontext import CPU, INTF, ViewContext
from supvisors.viewhandler import ViewHandler
from supvisors.viewhostaddress import HostAddressView
from supvisors.viewimage import address_cpu_img, address_io_img, address_mem_img
from supvisors.webutils import HOST_NODE_PAGE

from .base import DummyHttpContext


@pytest.fixture
def http_context():
    return DummyHttpContext('ui/hostaddress.html')


@pytest.fixture
def view(http_context):
    """ Fixture for the instance to test. """
    # apply the forced inheritance done in supvisors.plugin
    StatusView.__bases__ = (ViewHandler,)
    # create the instance to be tested
    return HostAddressView(http_context)


def test_init(view):
    """ Test the values set at construction. """
    assert view.page_name == HOST_NODE_PAGE


def test_write_contents_no_plot(mocker, view):
    """ Test the write_contents method. """
    mocked_network = mocker.patch('supvisors.viewhostaddress.HostAddressView.write_network_statistics')
    mocked_memory = mocker.patch('supvisors.viewhostaddress.HostAddressView.write_memory_statistics')
    mocked_processor = mocker.patch('supvisors.viewhostaddress.HostAddressView.write_processor_statistics')
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    # force import error on SupvisorsPlot
    mocker.patch.dict('sys.modules', {'supvisors.plot': None})
    # set context (meant to be set through render)
    dummy_stats = Mock(cpu='cpu', mem='mem', io='io')
    view.view_ctx = Mock(**{'get_node_stats.return_value': dummy_stats})
    # replace root structure
    mocked_root = Mock()
    # test call
    view.write_contents(mocked_root)
    assert mocked_processor.call_args_list == [call(mocked_root, 'cpu')]
    assert mocked_memory.call_args_list == [call(mocked_root, 'mem')]
    assert mocked_network.call_args_list == [call(mocked_root, 'io')]
    assert not mocked_export.called


def test_write_contents(mocker, view):
    """ Test the write_contents method. """
    # skip test if matplotlib is not installed
    pytest.importorskip('matplotlib', reason='cannot test as optional matplotlib is not installed')
    mocked_network = mocker.patch('supvisors.viewhostaddress.HostAddressView.write_network_statistics')
    mocked_memory = mocker.patch('supvisors.viewhostaddress.HostAddressView.write_memory_statistics')
    mocked_processor = mocker.patch('supvisors.viewhostaddress.HostAddressView.write_processor_statistics')
    mocked_io = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_io_image')
    mocked_mem = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_mem_image')
    mocked_cpu = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_cpu_image')
    # set context (meant to be set through render)
    dummy_stats = Mock(cpu='cpu', mem='mem', io='io')
    view.view_ctx = Mock(**{'get_node_stats.return_value': dummy_stats})
    # replace root structure
    mocked_root = Mock()
    # test call
    view.write_contents(mocked_root)
    assert mocked_processor.call_args_list == [call(mocked_root, 'cpu')]
    assert mocked_memory.call_args_list == [call(mocked_root, 'mem')]
    assert mocked_network.call_args_list == [call(mocked_root, 'io')]
    assert mocked_cpu.call_args_list == [call('cpu')]
    assert mocked_mem.call_args_list == [call('mem')]
    assert mocked_io.call_args_list == [call('io')]


def test_write_processor_single_title(view):
    """ Test the _write_processor_single_title method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html',
                            'cpu_id_to_string.return_value': '1'})  # replace root structure
    mocked_title_mid = Mock(attrib={})
    mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
    # in first call, elt is not the selected element
    view._write_processor_single_title(mocked_tr, 1, 0)
    assert mocked_tr.findmeld.call_args_list == [call('cpunum_a_mid')]
    assert mocked_title_mid.attrib == {}
    assert mocked_title_mid.attributes.call_args_list == [call(href='http://addr:port/index.html')]
    assert mocked_title_mid.content.call_args_list == [call('cpu#1')]
    mocked_tr.findmeld.reset_mock()
    mocked_title_mid.attributes.reset_mock()
    # in first call, elt is the selected element
    view._write_processor_single_title(mocked_tr, 1, 1)
    assert mocked_tr.findmeld.call_args_list == [call('cpunum_a_mid')]
    assert mocked_title_mid.attrib == {'class': 'button off active'}
    assert not mocked_title_mid.attributes.called
    assert mocked_title_mid.content.call_args_list == [call('cpu#1')]


def test_write_processor_single_statistics(mocker, view):
    """ Test the _write_processor_single_statistics method. """
    mocked_common = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_common_statistics')
    # replace root element
    mocked_root = Mock()
    # test method call
    view._write_processor_single_statistics(mocked_root, [1.523, 2.456])
    assert mocked_common.call_args_list == [call(mocked_root, [1.523, 2.456], 'cpuval_td_mid', 'cpuavg_td_mid',
                                                 'cpuslope_td_mid', 'cpudev_td_mid')]


def test_write_processor_statistics(mocker, view):
    """ Test the write_processor_statistics method. """
    mocked_stats = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_processor_single_statistics')
    mocked_title = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_processor_single_title')
    # set context (meant to be set through render)
    view.view_ctx = Mock(parameters={CPU: 1})
    # build root structure
    mocked_trs = [Mock(attrib={}) for _ in range(2)]
    mocked_mid = Mock(**{'repeat.return_value': [(mocked_trs[0], 'cpu stats 0'), (mocked_trs[1], 'cpu stats 1')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call
    view.write_processor_statistics(mocked_root, [])
    assert mocked_title.call_args_list == [call(mocked_trs[0], 1, 0), call(mocked_trs[1], 1, 1)]
    assert mocked_stats.call_args_list == [call(mocked_trs[0], 'cpu stats 0'), call(mocked_trs[1], 'cpu stats 1')]
    assert mocked_trs[0].attrib == {'class': 'brightened'}
    assert mocked_trs[1].attrib == {'class': 'shaded'}


def test_write_memory_statistics(mocker, view):
    """ Test the write_memory_statistics method. """
    mocked_common = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_common_statistics')
    # replace root element
    mocked_root = Mock()
    # test method call
    view.write_memory_statistics(mocked_root, [1.523, 2.456])
    assert mocked_common.call_args_list == [call(mocked_root, [1.523, 2.456], 'memval_td_mid', 'memavg_td_mid',
                                                 'memslope_td_mid', 'memdev_td_mid')]


def test_write_network_single_title(view):
    """ Test the _write_network_single_title method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html'})
    # replace root structure
    mocked_href_mid = Mock(attrib={})
    mocked_title_mid = Mock(attrib={}, **{'findmeld.return_value': mocked_href_mid})
    mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
    # in first call, elt is not the first line (rowspan False)
    view._write_network_single_title(mocked_tr, 'eth0', 'lo', False, True)
    assert mocked_tr.findmeld.call_args_list == [call('intf_td_mid')]
    assert mocked_title_mid.attrib == {}
    assert not mocked_title_mid.findmeld.called
    assert mocked_href_mid.attrib == {}
    assert mocked_title_mid.replace.call_args_list == [call('')]
    mocked_tr.findmeld.reset_mock()
    mocked_title_mid.replace.reset_mock()
    # in second call, elt is the first line (rowspan True), shaded and is not the selected interface
    view._write_network_single_title(mocked_tr, 'eth0', 'lo', True, True)
    assert mocked_tr.findmeld.call_args_list == [call('intf_td_mid')]
    assert mocked_title_mid.attrib == {'class': 'shaded', 'rowspan': '2'}
    assert mocked_title_mid.findmeld.call_args_list == [call('intf_a_mid')]
    assert mocked_href_mid.attrib == {}
    assert mocked_href_mid.attributes.call_args_list == [call(href='http://addr:port/index.html')]
    assert not mocked_title_mid.replace.called
    # reset context
    mocked_tr.findmeld.reset_mock()
    mocked_href_mid.attributes.reset_mock()
    mocked_title_mid.findmeld.reset_mock()
    del mocked_title_mid.attrib['class']
    # in third call, elt is the first line (rowspan True), not shaded and is the selected interface
    view._write_network_single_title(mocked_tr, 'lo', 'lo', True, False)
    assert mocked_tr.findmeld.call_args_list == [call('intf_td_mid')]
    assert mocked_title_mid.attrib == {'class': 'brightened', 'rowspan': '2'}
    assert mocked_title_mid.findmeld.call_args_list == [call('intf_a_mid')]
    assert mocked_href_mid.attrib == {'class': 'button off active'}
    assert not mocked_href_mid.attributes.called
    assert not mocked_title_mid.replace.called


def test_write_network_single_statistics(mocker, view):
    """ Test the _write_network_single_statistics method. """
    mocked_common = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_common_statistics')
    # replace root structure
    mocked_title_mid = Mock()
    mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
    # in first call, test no rate, slope and standard deviation
    view._write_network_single_statistics(mocked_tr, [1.523, 2.456], False)
    assert mocked_tr.findmeld.call_args_list == [call('intfrxtx_td_mid')]
    assert mocked_title_mid.content.call_args_list == [call('Tx')]
    assert mocked_common.call_args_list == [call(mocked_tr, [1.523, 2.456], 'intfval_td_mid', 'intfavg_td_mid',
                                                 'intfslope_td_mid', 'intfdev_td_mid')]
    mocked_tr.reset_mock()
    mocked_title_mid.content.reset_mock()
    mocked_common.reset_mock()
    # in second call, test no rate, slope and standard deviation
    view._write_network_single_statistics(mocked_tr, [1.523, 2.456], True)
    assert mocked_tr.findmeld.call_args_list == [call('intfrxtx_td_mid')]
    assert mocked_title_mid.content.call_args_list == [call('Rx')]
    assert mocked_common.call_args_list == [call(mocked_tr, [1.523, 2.456], 'intfval_td_mid', 'intfavg_td_mid',
                                                 'intfslope_td_mid', 'intfdev_td_mid')]


def test_write_network_statistics(mocker, view):
    """ Test the write_network_statistics method. """
    mocked_stats = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_network_single_statistics')
    mocked_title = mocker.patch('supvisors.viewhostaddress.HostAddressView._write_network_single_title')
    # set context (meant to be set through render)
    view.view_ctx = Mock(parameters={INTF: 'eth0'})
    # build root structure
    mocked_trs = [Mock(attrib={}) for _ in range(4)]
    mocked_mid = Mock(**{'repeat.return_value': [(mocked_trs[0], ('lo', 'lo recv')),
                                                 (mocked_trs[1], ('lo', 'lo sent')),
                                                 (mocked_trs[2], ('eth0', 'eth0 recv')),
                                                 (mocked_trs[3], ('eth0', 'eth0 sent'))]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test method with dummy stats
    dummy_stats = {'lo': ['lo recv', 'lo sent'], 'eth0': ['eth0 recv', 'eth0 sent']}
    view.write_network_statistics(mocked_root, dummy_stats)
    # check calls
    assert mocked_root.findmeld.call_args_list == [call('intf_tr_mid')]
    assert mocked_mid.repeat.call_args_list == [call([('lo', 'lo recv'), ('lo', 'lo sent'),
                                                      ('eth0', 'eth0 recv'), ('eth0', 'eth0 sent')])]
    assert mocked_trs[0].attrib['class'] == 'brightened'
    assert mocked_trs[1].attrib['class'] == 'brightened'
    assert mocked_trs[2].attrib['class'] == 'shaded'
    assert mocked_trs[3].attrib['class'] == 'shaded'
    assert mocked_title.call_args_list == [call(mocked_trs[0], 'eth0', 'lo', True, False),
                                           call(mocked_trs[1], 'eth0', 'lo', False, False),
                                           call(mocked_trs[2], 'eth0', 'eth0', True, True),
                                           call(mocked_trs[3], 'eth0', 'eth0', False, True)]
    assert mocked_stats.call_args_list == [call(mocked_trs[0], 'lo recv', True),
                                           call(mocked_trs[1], 'lo sent', False),
                                           call(mocked_trs[2], 'eth0 recv', True),
                                           call(mocked_trs[3], 'eth0 sent', False)]


def test_write_common_statistics(mocker, view):
    """ Test the _write_common_statistics method. """
    mocked_class = mocker.patch('supvisors.viewhostaddress.HostAddressView.set_slope_class')
    mocked_stats = mocker.patch('supvisors.viewhostaddress.get_stats',
                                side_effect=[(10.231, None, (None, 2), None), (8.999, 2, (-1.1, 4), 5.72)])
    # replace root structure
    mocked_val_mid = Mock()
    mocked_avg_mid = Mock()
    mocked_slope_mid = Mock()
    mocked_dev_mid = Mock()
    mocked_tr = Mock(**{'findmeld.side_effect': [mocked_val_mid, mocked_avg_mid,
                                                 mocked_val_mid, mocked_avg_mid,
                                                 mocked_slope_mid, mocked_dev_mid]})
    # in first call, test empty stats
    view._write_common_statistics(mocked_tr, [], 'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
    assert not mocked_tr.findmeld.called
    assert not mocked_stats.called
    assert not mocked_class.called
    assert not mocked_val_mid.called
    assert not mocked_avg_mid.called
    assert not mocked_slope_mid.called
    assert not mocked_dev_mid.called
    # in second call, test no rate, slope and standard deviation
    view._write_common_statistics(mocked_tr, [1.523, 2.456], 'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
    assert mocked_tr.findmeld.call_args_list == [call('val_mid'), call('avg_mid')]
    assert mocked_stats.call_args_list == [call([1.523, 2.456])]
    assert not mocked_class.called
    assert mocked_val_mid.content.call_args_list == [call('2.46')]
    assert mocked_avg_mid.content.call_args_list == [call('10.23')]
    assert not mocked_slope_mid.called
    assert not mocked_dev_mid.called
    mocked_stats.reset_mock()
    mocked_val_mid.content.reset_mock()
    mocked_avg_mid.content.reset_mock()
    # in third call, test no rate, slope and standard deviation
    view._write_common_statistics(mocked_tr, [1.523, 2.456], 'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
    assert mocked_stats.call_args_list == [call([1.523, 2.456])]
    assert mocked_class.call_args_list == [call(mocked_val_mid, 2)]
    assert mocked_tr.findmeld.call_args_list == [call('val_mid'), call('avg_mid'),
                                                 call('val_mid'), call('avg_mid'), call('slope_mid'), call('dev_mid')]
    assert mocked_val_mid.content.call_args_list == [call('2.46')]
    assert mocked_avg_mid.content.call_args_list == [call('9.00')]
    assert mocked_slope_mid.content.call_args_list == [call('-1.10')]
    assert mocked_dev_mid.content.call_args_list == [call('5.72')]


def test_write_cpu_image(mocker, view):
    """ Test the _write_cpu_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_add = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    # set context (meant to be set through render)
    view.view_ctx = Mock(parameters={CPU: 0}, **{'cpu_id_to_string.return_value': ViewContext.cpu_id_to_string(0)})
    # just test calls to StatisticsPlot
    dummy_stats = ['#all stats', '#0 stats', '#1 stats']
    view._write_cpu_image(dummy_stats)
    assert mocked_add.call_args_list == [call('CPU #all', '%', '#all stats')]
    assert mocked_export.call_args_list == [call(address_cpu_img)]


def test_write_mem_image(mocker, view):
    """ Test the _write_mem_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_add = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    # just test calls to StatisticsPlot
    dummy_stats = ['mem 1', 'mem 2']
    view._write_mem_image(dummy_stats)
    assert mocked_add.call_args_list == [call('MEM', '%', dummy_stats)]
    assert mocked_export.call_args_list == [call(address_mem_img)]


def test_write_io_image(mocker, view):
    """ Test the _write_io_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_add = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    # set context (meant to be set through render)
    view.view_ctx = Mock(parameters={INTF: 'eth0'})
    # just test calls to StatisticsPlot
    dummy_stats = {'lo': ['lo recv', 'lo sent'], 'eth0': ['eth0 recv', 'eth0 sent']}
    view._write_io_image(dummy_stats)
    assert mocked_add.call_args_list == [call('eth0 recv', 'kbits/s', 'eth0 recv'),
                                         call('eth0 sent', 'kbits/s', 'eth0 sent')]
    assert mocked_export.call_args_list == [call(address_io_img)]
