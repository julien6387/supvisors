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

from unittest.mock import call, Mock

import pytest

from supvisors.statscollector import LocalNodeInfo
from supvisors.web.viewcontext import ViewContext
from supvisors.web.viewhostinstance import HostInstanceView
from supvisors.web.viewimage import (host_cpu_img, host_net_io_img, host_mem_img,
                                     host_disk_io_img, host_disk_usage_img)
from supvisors.web.webutils import HOST_INSTANCE_PAGE, PROC_INSTANCE_PAGE
from .base import DummyHttpContext
from .conftest import create_element


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext('ui/host_instance.html')
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


@pytest.fixture
def view(http_context):
    """ Fixture for the instance to test. """
    # create the instance to be tested
    return HostInstanceView(http_context)


def test_init(view):
    """ Test the values set at construction. """
    assert view.page_name == HOST_INSTANCE_PAGE


def test_write_options(mocker, view):
    """ Test the ApplicationView.write_options method. """
    mocked_period = mocker.patch.object(view, 'write_periods')
    mocked_switch = mocker.patch.object(view, 'write_view_switch')
    mocked_header = Mock()
    view.write_options(mocked_header)
    assert mocked_period.call_args_list == [call(mocked_header)]
    assert mocked_switch.call_args_list == [call(mocked_header)]


def test_write_view_switch(supvisors, view):
    """ Test the SupvisorsInstanceView.write_view_switch method. """
    # set context (meant to be set through constructor and render)
    view.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    supvisors.mapper.local_identifier = '10.0.0.1:25000'
    # build root structure
    mocked_process_view_mid = create_element()
    mocked_host_view_mid = create_element()
    mocked_header = create_element({'process_view_a_mid': mocked_process_view_mid,
                                    'host_view_a_mid': mocked_host_view_mid})
    # test call when SupvisorsInstanceView is a host page
    view.page_name = HOST_INSTANCE_PAGE
    view.write_view_switch(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('process_view_a_mid'), call('host_view_a_mid'), ]
    assert view.view_ctx.format_url.call_args_list == [call('', PROC_INSTANCE_PAGE)]
    assert mocked_process_view_mid.attributes.call_args_list == [call(href='an url')]
    assert mocked_host_view_mid.content.call_args_list == [call('10.0.0.1')]


def test_write_contents_no_plot(mocker, supvisors, view):
    """ Test the write_contents method in the context where psutil is not installed. """
    mocked_characteristics = mocker.patch.object(view, 'write_node_characteristics')
    mocked_processor = mocker.patch.object(view, 'write_processor_statistics')
    mocked_memory = mocker.patch.object(view, 'write_memory_statistics')
    mocked_network = mocker.patch.object(view, 'write_network_io_statistics')
    mocked_disk = mocker.patch.object(view, 'write_disk_statistics')
    mocked_cpu_img = mocker.patch.object(view, '_write_cpu_image', side_effect=ImportError)
    mocked_mem_img = mocker.patch.object(view, '_write_mem_image')
    mocked_net_io_img = mocker.patch.object(view, '_write_net_io_image')
    mocked_disk_img = mocker.patch.object(view, '_write_disk_image')
    # set context (meant to be set through render)
    dummy_stats = Mock(cpu='cpu', mem='mem', net_io='net_io', times='times')
    view.view_ctx = Mock(**{'get_instance_stats.return_value': dummy_stats,
                            'get_node_characteristics.return_value': supvisors.stats_collector.node_info})
    # create xhtml structure
    cpu_image_fig_mid = create_element()
    mem_image_fig_mid = create_element()
    net_io_image_fig_mid = create_element()
    disk_io_image_fig_mid = create_element()
    disk_usage_image_fig_mid = create_element()
    contents_elt = create_element({'cpu_image_fig_mid': cpu_image_fig_mid,
                                   'mem_image_fig_mid': mem_image_fig_mid,
                                   'net_io_image_fig_mid': net_io_image_fig_mid,
                                   'disk_io_image_fig_mid': disk_io_image_fig_mid,
                                   'disk_usage_image_fig_mid': disk_usage_image_fig_mid})
    # test call
    view.write_contents(contents_elt)
    assert mocked_characteristics.call_args_list == [call(contents_elt, supvisors.stats_collector.node_info)]
    assert mocked_processor.call_args_list == [call(contents_elt, 'cpu', 'times')]
    assert mocked_memory.call_args_list == [call(contents_elt, 'mem', 'times')]
    assert mocked_network.call_args_list == [call(contents_elt, 'net_io')]
    assert mocked_disk.call_args_list == [call(contents_elt, dummy_stats)]
    assert mocked_cpu_img.call_args_list == [call('cpu', 'times')]
    assert not mocked_mem_img.called
    assert not mocked_net_io_img.called
    assert not mocked_disk_img.called
    assert contents_elt.findmeld.call_args_list == [call('cpu_image_fig_mid'),
                                                    call('mem_image_fig_mid'),
                                                    call('net_io_image_fig_mid'),
                                                    call('disk_io_image_fig_mid'),
                                                    call('disk_usage_image_fig_mid')]
    assert cpu_image_fig_mid.replace.call_args_list == [call('')]
    assert mem_image_fig_mid.replace.call_args_list == [call('')]
    assert net_io_image_fig_mid.replace.call_args_list == [call('')]
    assert disk_io_image_fig_mid.replace.call_args_list == [call('')]
    assert disk_usage_image_fig_mid.replace.call_args_list == [call('')]


def test_write_contents(mocker, supvisors, view):
    """ Test the write_contents method. """
    # skip test if matplotlib is not installed
    pytest.importorskip('matplotlib', reason='cannot test as optional matplotlib is not installed')
    mocked_characteristics = mocker.patch.object(view, 'write_node_characteristics')
    mocked_processor = mocker.patch.object(view, 'write_processor_statistics')
    mocked_memory = mocker.patch.object(view, 'write_memory_statistics')
    mocked_network = mocker.patch.object(view, 'write_network_io_statistics')
    mocked_disk = mocker.patch.object(view, 'write_disk_statistics')
    mocked_cpu_img = mocker.patch.object(view, '_write_cpu_image')
    mocked_mem_img = mocker.patch.object(view, '_write_mem_image')
    mocked_net_io_img = mocker.patch.object(view, '_write_net_io_image')
    mocked_disk_img = mocker.patch.object(view, '_write_disk_image')
    # set context (meant to be set through render)
    dummy_stats = Mock(cpu='cpu', mem='mem', net_io='net_io', times='times')
    view.view_ctx = Mock(**{'get_instance_stats.return_value': dummy_stats,
                            'get_node_characteristics.return_value': supvisors.stats_collector.node_info})
    # create xhtml structure
    cpu_image_fig_mid = create_element()
    mem_image_fig_mid = create_element()
    net_io_image_fig_mid = create_element()
    disk_io_image_fig_mid = create_element()
    disk_usage_image_fig_mid = create_element()
    contents_elt = create_element({'cpu_image_fig_mid': cpu_image_fig_mid,
                                   'mem_image_fig_mid': mem_image_fig_mid,
                                   'net_io_image_fig_mid': net_io_image_fig_mid,
                                   'disk_io_image_fig_mid': disk_io_image_fig_mid,
                                   'disk_usage_image_fig_mid': disk_usage_image_fig_mid})
    # test call
    view.write_contents(contents_elt)
    assert mocked_characteristics.call_args_list == [call(contents_elt, supvisors.stats_collector.node_info)]
    assert mocked_processor.call_args_list == [call(contents_elt, 'cpu', 'times')]
    assert mocked_memory.call_args_list == [call(contents_elt, 'mem', 'times')]
    assert mocked_network.call_args_list == [call(contents_elt, 'net_io')]
    assert mocked_disk.call_args_list == [call(contents_elt, dummy_stats)]
    assert mocked_cpu_img.call_args_list == [call('cpu', 'times')]
    assert mocked_mem_img.call_args_list == [call('mem', 'times')]
    assert mocked_net_io_img.call_args_list == [call('net_io')]
    assert mocked_disk_img.call_args_list == [call(dummy_stats)]
    assert not contents_elt.findmeld.called
    assert not cpu_image_fig_mid.replace.called
    assert not mem_image_fig_mid.replace.called
    assert not net_io_image_fig_mid.replace.called
    assert not disk_io_image_fig_mid.replace.called
    assert not disk_usage_image_fig_mid.replace.called


def test_write_node_characteristics(mocker, supvisors, view):
    """ Test the write_node_characteristics method. """
    # patch psutil functions
    mocker.patch('psutil.cpu_count', return_value=4)
    mocker.patch('psutil.cpu_freq', return_value=Mock(current=3000.01))
    mocker.patch('psutil.virtual_memory', return_value=Mock(total=16123456789))
    # create the xhtml structure
    node_td_mid = create_element()
    ipaddress_td_mid = create_element()
    cpu_count_td_mid = create_element()
    cpu_freq_td_mid = create_element()
    physical_mem_td_mid = create_element()
    contents_elt = create_element({'node_td_mid': node_td_mid, 'ipaddress_td_mid': ipaddress_td_mid,
                                   'cpu_count_td_mid': cpu_count_td_mid, 'cpu_freq_td_mid': cpu_freq_td_mid,
                                   'physical_mem_td_mid': physical_mem_td_mid})
    # change local node
    supvisors.mapper.local_identifier = '10.0.0.1:25000'
    # test call
    node_info = LocalNodeInfo()
    view.write_node_characteristics(contents_elt, node_info)
    assert node_td_mid.content.call_args_list == [call('10.0.0.1')]
    assert ipaddress_td_mid.content.call_args_list == [call('10.0.0.1')]
    assert cpu_count_td_mid.content.call_args_list == [call('4 / 4')]
    assert cpu_freq_td_mid.content.call_args_list == [call('3000 MHz')]
    assert physical_mem_td_mid.content.call_args_list == [call('15.02 GiB')]


def test_write_processor_single_title(view):
    """ Test the _write_processor_single_title method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html',
                            'cpu_id_to_string.return_value': '1'})  # replace root structure
    mocked_title_mid = Mock(attrib={})
    mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
    # in first call, elt is not the selected element
    view._write_processor_single_title(mocked_tr, 1, 0)
    assert mocked_tr.findmeld.call_args_list == [call('cpu_num_a_mid')]
    assert mocked_title_mid.attrib == {}
    assert mocked_title_mid.attributes.call_args_list == [call(href='http://addr:port/index.html')]
    assert mocked_title_mid.content.call_args_list == [call('cpu#1')]
    mocked_tr.findmeld.reset_mock()
    mocked_title_mid.attributes.reset_mock()
    # in first call, elt is the selected element
    view._write_processor_single_title(mocked_tr, 1, 1)
    assert mocked_tr.findmeld.call_args_list == [call('cpu_num_a_mid')]
    assert mocked_title_mid.attrib == {'class': 'button off active'}
    assert not mocked_title_mid.attributes.called
    assert mocked_title_mid.content.call_args_list == [call('cpu#1')]


def test_write_processor_single_statistics(mocker, view):
    """ Test the _write_processor_single_statistics method. """
    mocked_common = mocker.patch.object(view, '_write_common_detailed_statistics')
    # replace root element
    mocked_root = Mock()
    # test method call
    view._write_processor_single_statistics(mocked_root, [1.523, 2.456], [1, 2, 3])
    assert mocked_common.call_args_list == [call(mocked_root, [1.523, 2.456], [1, 2, 3],
                                                 'cpu_val_td_mid', 'cpu_avg_td_mid',
                                                 'cpu_slope_td_mid', 'cpu_dev_td_mid')]


def test_write_processor_statistics(mocker, view):
    """ Test the write_processor_statistics method. """
    mocked_stats = mocker.patch.object(view, '_write_processor_single_statistics')
    mocked_title = mocker.patch.object(view, '_write_processor_single_title')
    # set context (meant to be set through render)
    view.view_ctx = Mock(cpu_id=1)
    # build root structure
    mocked_trs = [Mock(attrib={}) for _ in range(2)]
    mocked_mid = Mock(**{'repeat.return_value': [(mocked_trs[0], 'cpu stats 0'), (mocked_trs[1], 'cpu stats 1')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call
    view.write_processor_statistics(mocked_root, [], [1, 2, 3])
    assert mocked_title.call_args_list == [call(mocked_trs[0], 1, 0), call(mocked_trs[1], 1, 1)]
    assert mocked_stats.call_args_list == [call(mocked_trs[0], 'cpu stats 0', [1, 2, 3]),
                                           call(mocked_trs[1], 'cpu stats 1', [1, 2, 3])]
    assert mocked_trs[0].attrib == {'class': 'brightened'}
    assert mocked_trs[1].attrib == {'class': 'shaded'}


def test_write_memory_statistics(mocker, view):
    """ Test the write_memory_statistics method. """
    mocked_common = mocker.patch.object(view, '_write_common_detailed_statistics')
    # replace root element
    mocked_root = Mock()
    # test method call
    view.write_memory_statistics(mocked_root, [1.523, 2.456], [1, 2, 3])
    assert mocked_common.call_args_list == [call(mocked_root, [1.523, 2.456], [1, 2, 3],
                                                 'mem_val_td_mid', 'mem_avg_td_mid',
                                                 'mem_slope_td_mid', 'mem_dev_td_mid')]


def test_write_network_io_single_title(view):
    """ Test the _write_network_io_single_title method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html'})
    # replace root structure
    net_io_nic_a_mid = create_element()
    net_io_nic_td_mid = create_element({'net_io_nic_a_mid': net_io_nic_a_mid})
    tr_elt = create_element({'net_io_nic_td_mid': net_io_nic_td_mid})
    # in first call, elt is not the first line (rowspan False)
    view._write_network_io_single_title(tr_elt, 'eth0', 'lo', False, True)
    assert tr_elt.findmeld.call_args_list == [call('net_io_nic_td_mid')]
    assert net_io_nic_td_mid.attrib == {'class': ''}
    assert not net_io_nic_td_mid.findmeld.called
    assert net_io_nic_a_mid.attrib == {'class': ''}
    assert net_io_nic_td_mid.replace.call_args_list == [call('')]
    tr_elt.reset_all()
    # in second call, elt is the first line (rowspan True), shaded and is not the selected interface
    view._write_network_io_single_title(tr_elt, 'eth0', 'lo', True, True)
    assert tr_elt.findmeld.call_args_list == [call('net_io_nic_td_mid')]
    assert net_io_nic_td_mid.attrib == {'class': 'shaded', 'rowspan': '2'}
    assert net_io_nic_td_mid.findmeld.call_args_list == [call('net_io_nic_a_mid')]
    assert net_io_nic_a_mid.attrib == {'class': ''}
    assert net_io_nic_a_mid.attributes.call_args_list == [call(href='http://addr:port/index.html')]
    assert not net_io_nic_td_mid.replace.called
    # reset context
    tr_elt.reset_all()
    # in third call, elt is the first line (rowspan True), not shaded and is the selected interface
    view._write_network_io_single_title(tr_elt, 'lo', 'lo', True, False)
    assert tr_elt.findmeld.call_args_list == [call('net_io_nic_td_mid')]
    assert net_io_nic_td_mid.attrib == {'class': 'brightened', 'rowspan': '2'}
    assert net_io_nic_td_mid.findmeld.call_args_list == [call('net_io_nic_a_mid')]
    assert net_io_nic_a_mid.attrib == {'class': 'button off active'}
    assert not net_io_nic_a_mid.attributes.called
    assert not net_io_nic_td_mid.replace.called


def test_write_network_io_single_statistics(mocker, view):
    """ Test the _write_network_io_single_statistics method. """
    mocked_common = mocker.patch.object(view, '_write_common_detailed_statistics')
    # replace root structure
    net_io_rxtx_td_mid = create_element()
    tr_elt = create_element({'net_io_rxtx_td_mid': net_io_rxtx_td_mid})
    # test send bytes
    view._write_network_io_single_statistics(tr_elt, [1.523, 2.456], [1, 2, 3], False)
    assert tr_elt.findmeld.call_args_list == [call('net_io_rxtx_td_mid')]
    assert net_io_rxtx_td_mid.content.call_args_list == [call('Tx')]
    assert mocked_common.call_args_list == [call(tr_elt, [1.523, 2.456], [1, 2, 3],
                                                 'net_io_val_td_mid', 'net_io_avg_td_mid',
                                                 'net_io_slope_td_mid', 'net_io_dev_td_mid')]
    tr_elt.reset_all()
    mocker.resetall()
    # test recv bytes
    view._write_network_io_single_statistics(tr_elt, [1.523, 2.456], [1, 2, 3], True)
    assert tr_elt.findmeld.call_args_list == [call('net_io_rxtx_td_mid')]
    assert net_io_rxtx_td_mid.content.call_args_list == [call('Rx')]
    assert mocked_common.call_args_list == [call(tr_elt, [1.523, 2.456], [1, 2, 3],
                                                 'net_io_val_td_mid', 'net_io_avg_td_mid',
                                                 'net_io_slope_td_mid', 'net_io_dev_td_mid')]


def test_write_network_io_statistics(mocker, view):
    """ Test the write_network_io_statistics method. """
    mocked_stats = mocker.patch.object(view, '_write_network_io_single_statistics')
    mocked_title = mocker.patch.object(view, '_write_network_io_single_title')
    # set context (meant to be set through render)
    view.view_ctx = Mock(nic_name='eth0')
    # build root structure
    net_io_tr_elts = [create_element() for _ in range(4)]
    net_io_tr_mid = create_element()
    net_io_tr_mid.repeat.return_value = [(net_io_tr_elts[0], ('lo', [1, 2, 3], 'lo recv')),
                                         (net_io_tr_elts[1], ('lo', [1, 2, 3], 'lo sent')),
                                         (net_io_tr_elts[2], ('eth0', [2, 3], 'eth0 recv')),
                                         (net_io_tr_elts[3], ('eth0', [2, 3], 'eth0 sent'))]
    tr_elt = create_element({'net_io_tr_mid': net_io_tr_mid})
    # test method with dummy stats
    dummy_io_stats = {'lo': [[1, 2, 3], ['lo recv', 'lo sent']],
                      'eth0': [[2, 3], ['eth0 recv', 'eth0 sent']]}
    view.write_network_io_statistics(tr_elt, dummy_io_stats)
    # check calls
    assert tr_elt.findmeld.call_args_list == [call('net_io_tr_mid')]
    assert net_io_tr_mid.repeat.call_args_list == [call([('lo', [1, 2, 3], 'lo recv'),
                                                         ('lo', [1, 2, 3], 'lo sent'),
                                                         ('eth0', [2, 3], 'eth0 recv'),
                                                         ('eth0', [2, 3], 'eth0 sent')])]
    assert net_io_tr_elts[0].attrib['class'] == 'brightened'
    assert net_io_tr_elts[1].attrib['class'] == 'brightened'
    assert net_io_tr_elts[2].attrib['class'] == 'shaded'
    assert net_io_tr_elts[3].attrib['class'] == 'shaded'
    assert mocked_title.call_args_list == [call(net_io_tr_elts[0], 'eth0', 'lo', True, False),
                                           call(net_io_tr_elts[1], 'eth0', 'lo', False, False),
                                           call(net_io_tr_elts[2], 'eth0', 'eth0', True, True),
                                           call(net_io_tr_elts[3], 'eth0', 'eth0', False, True)]
    assert mocked_stats.call_args_list == [call(net_io_tr_elts[0], 'lo recv', [1, 2, 3], True),
                                           call(net_io_tr_elts[1], 'lo sent', [1, 2, 3], False),
                                           call(net_io_tr_elts[2], 'eth0 recv', [2, 3], True),
                                           call(net_io_tr_elts[3], 'eth0 sent', [2, 3], False)]


def test_write_disk_io_single_title(view):
    """ Test the _write_disk_io_single_title method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html'})
    # replace root structure
    disk_io_device_a_mid = create_element()
    disk_io_device_td_mid = create_element({'disk_io_device_a_mid': disk_io_device_a_mid})
    tr_elt = create_element({'disk_io_device_td_mid': disk_io_device_td_mid})
    # in first call, elt is not the first line (rowspan False)
    view._write_disk_io_single_title(tr_elt, 'sdb', 'sda', False, True)
    assert tr_elt.findmeld.call_args_list == [call('disk_io_device_td_mid')]
    assert disk_io_device_td_mid.attrib == {'class': ''}
    assert not disk_io_device_td_mid.findmeld.called
    assert disk_io_device_a_mid.attrib == {'class': ''}
    assert disk_io_device_td_mid.replace.call_args_list == [call('')]
    tr_elt.reset_all()
    # in second call, elt is the first line (rowspan True), shaded and is not the selected interface
    view._write_disk_io_single_title(tr_elt, 'sdb', 'sda', True, True)
    assert tr_elt.findmeld.call_args_list == [call('disk_io_device_td_mid')]
    assert disk_io_device_td_mid.attrib == {'class': 'shaded', 'rowspan': '2'}
    assert disk_io_device_td_mid.findmeld.call_args_list == [call('disk_io_device_a_mid')]
    assert disk_io_device_a_mid.attrib == {'class': ''}
    assert disk_io_device_a_mid.attributes.call_args_list == [call(href='http://addr:port/index.html')]
    assert not disk_io_device_td_mid.replace.called
    tr_elt.reset_all()
    # in third call, elt is the first line (rowspan True), not shaded and is the selected interface
    view._write_disk_io_single_title(tr_elt, 'sda', 'sda', True, False)
    assert tr_elt.findmeld.call_args_list == [call('disk_io_device_td_mid')]
    assert disk_io_device_td_mid.attrib == {'class': 'brightened', 'rowspan': '2'}
    assert disk_io_device_td_mid.findmeld.call_args_list == [call('disk_io_device_a_mid')]
    assert disk_io_device_a_mid.attrib == {'class': 'button off active'}
    assert not disk_io_device_a_mid.attributes.called
    assert not disk_io_device_td_mid.replace.called


def test_write_disk_io_single_statistics(mocker, view):
    """ Test the _write_disk_io_single_statistics method. """
    mocked_common = mocker.patch.object(view, '_write_common_detailed_statistics')
    # replace root structure
    disk_io_rw_td_mid = create_element()
    tr_elt = create_element({'disk_io_rw_td_mid': disk_io_rw_td_mid})
    # test send bytes
    view._write_disk_io_single_statistics(tr_elt, [1.523, 2.456], [1, 2, 3], False)
    assert tr_elt.findmeld.call_args_list == [call('disk_io_rw_td_mid')]
    assert disk_io_rw_td_mid.content.call_args_list == [call('W')]
    assert mocked_common.call_args_list == [call(tr_elt, [1.523, 2.456], [1, 2, 3],
                                                 'disk_io_val_td_mid', 'disk_io_avg_td_mid',
                                                 'disk_io_slope_td_mid', 'disk_io_dev_td_mid')]
    tr_elt.reset_all()
    mocker.resetall()
    # test recv bytes
    view._write_disk_io_single_statistics(tr_elt, [1.523, 2.456], [1, 2, 3], True)
    assert tr_elt.findmeld.call_args_list == [call('disk_io_rw_td_mid')]
    assert disk_io_rw_td_mid.content.call_args_list == [call('R')]
    assert mocked_common.call_args_list == [call(tr_elt, [1.523, 2.456], [1, 2, 3],
                                                 'disk_io_val_td_mid', 'disk_io_avg_td_mid',
                                                 'disk_io_slope_td_mid', 'disk_io_dev_td_mid')]


def test_write_disk_io_statistics(mocker, view):
    """ Test the write_disk_io_statistics method. """
    mocked_stats = mocker.patch.object(view, '_write_disk_io_single_statistics')
    mocked_title = mocker.patch.object(view, '_write_disk_io_single_title')
    # set context (meant to be set through render)
    view.view_ctx = Mock(device='sdb')
    # build root structure
    disk_io_tr_elts = [create_element() for _ in range(4)]
    disk_io_tr_mid = create_element()
    disk_io_tr_mid.repeat.return_value = [(disk_io_tr_elts[0], ('sda', [1, 2, 3], 'sda read')),
                                          (disk_io_tr_elts[1], ('sda', [1, 2, 3], 'sda write')),
                                          (disk_io_tr_elts[2], ('sdb', [2, 3], 'sdb read')),
                                          (disk_io_tr_elts[3], ('sdb', [2, 3], 'sdb write'))]
    tr_elt = create_element({'disk_io_tr_mid': disk_io_tr_mid})
    # test method with dummy stats
    dummy_io_stats = {'sda': [[1, 2, 3], ['sda read', 'sda write']],
                      'sdb': [[2, 3], ['sdb read', 'sdb write']]}
    view.write_disk_io_statistics(tr_elt, dummy_io_stats)
    # check calls
    assert tr_elt.findmeld.call_args_list == [call('disk_io_tr_mid')]
    assert disk_io_tr_mid.repeat.call_args_list == [call([('sda', [1, 2, 3], 'sda read'),
                                                          ('sda', [1, 2, 3], 'sda write'),
                                                          ('sdb', [2, 3], 'sdb read'),
                                                          ('sdb', [2, 3], 'sdb write')])]
    assert disk_io_tr_elts[0].attrib['class'] == 'brightened'
    assert disk_io_tr_elts[1].attrib['class'] == 'brightened'
    assert disk_io_tr_elts[2].attrib['class'] == 'shaded'
    assert disk_io_tr_elts[3].attrib['class'] == 'shaded'
    assert mocked_title.call_args_list == [call(disk_io_tr_elts[0], 'sdb', 'sda', True, False),
                                           call(disk_io_tr_elts[1], 'sdb', 'sda', False, False),
                                           call(disk_io_tr_elts[2], 'sdb', 'sdb', True, True),
                                           call(disk_io_tr_elts[3], 'sdb', 'sdb', False, True)]
    assert mocked_stats.call_args_list == [call(disk_io_tr_elts[0], 'sda read', [1, 2, 3], True),
                                           call(disk_io_tr_elts[1], 'sda write', [1, 2, 3], False),
                                           call(disk_io_tr_elts[2], 'sdb read', [2, 3], True),
                                           call(disk_io_tr_elts[3], 'sdb write', [2, 3], False)]


def test_write_disk_usage_single_title(view):
    """ Test the _write_disk_usage_single_title method. """
    # set context (meant to be set through render)
    view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html'})
    # replace root structure
    disk_usage_partition_a_mid = create_element()
    tr_elt = create_element({'disk_usage_partition_a_mid': disk_usage_partition_a_mid})
    # in first call, elt is not the selected partition
    view._write_disk_usage_single_title(tr_elt, '/root', '/')
    assert tr_elt.findmeld.call_args_list == [call('disk_usage_partition_a_mid')]
    assert disk_usage_partition_a_mid.attrib == {'class': ''}
    assert disk_usage_partition_a_mid.attributes.call_args_list == [call(href='http://addr:port/index.html')]
    tr_elt.reset_all()
    # in second call, elt is the selected partition
    view._write_disk_usage_single_title(tr_elt, '/root', '/root')
    assert tr_elt.findmeld.call_args_list == [call('disk_usage_partition_a_mid')]
    assert disk_usage_partition_a_mid.attrib == {'class': 'button off active'}
    assert not disk_usage_partition_a_mid.attributes.called


def test_write_disk_usage_single_statistics(mocker, view):
    """ Test the _write_disk_usage_single_statistics method. """
    mocked_common = mocker.patch.object(view, '_write_common_detailed_statistics')
    # replace root structure
    tr_elt = create_element()
    # test call
    view._write_disk_usage_single_statistics(tr_elt, [1.523, 2.456], [1, 2, 3])
    assert mocked_common.call_args_list == [call(tr_elt, [1.523, 2.456], [1, 2, 3],
                                                 'disk_usage_val_td_mid', 'disk_usage_avg_td_mid',
                                                 'disk_usage_slope_td_mid', 'disk_usage_dev_td_mid')]


def test_write_disk_usage_statistics(mocker, view):
    """ Test the write_disk_usage_statistics method. """
    mocked_stats = mocker.patch.object(view, '_write_disk_usage_single_statistics')
    mocked_title = mocker.patch.object(view, '_write_disk_usage_single_title')
    # set context (meant to be set through render)
    view.view_ctx = Mock(partition='/root')
    # build root structure
    disk_usage_tr_elts = [create_element() for _ in range(2)]
    disk_usage_tr_mid = create_element()
    disk_usage_tr_mid.repeat.return_value = [(disk_usage_tr_elts[0], ['/', [[1, 2, 3], ['disk usage stats /']]]),
                                             (disk_usage_tr_elts[1], ['/root', [[2, 3], ['disk usage stats /root']]])]
    mocked_root = create_element({'disk_usage_tr_mid': disk_usage_tr_mid})
    # test call
    view.write_disk_usage_statistics(mocked_root, Mock())
    assert mocked_title.call_args_list == [call(disk_usage_tr_elts[0], '/root', '/'),
                                           call(disk_usage_tr_elts[1], '/root', '/root')]
    assert mocked_stats.call_args_list == [call(disk_usage_tr_elts[0], 'disk usage stats /', [1, 2, 3]),
                                           call(disk_usage_tr_elts[1], 'disk usage stats /root', [2, 3])]
    assert disk_usage_tr_elts[0].attrib == {'class': 'brightened'}
    assert disk_usage_tr_elts[1].attrib == {'class': 'shaded'}


def test_write_disk_statistics(mocker, view):
    """ Test the write_disk_statistics method. """
    mocked_usage = mocker.patch.object(view, 'write_disk_usage_statistics')
    mocked_io = mocker.patch.object(view, 'write_disk_io_statistics')
    # set context (meant to be set through render)
    stats = Mock(disk_usage='disk usage', disk_io='disk io')
    # create xhtml structure
    disk_io_div_mid = create_element()
    disk_io_view_mid = create_element()
    disk_usage_div_mid = create_element()
    disk_usage_view_mid = create_element()
    contents_elt = create_element({'disk_io_div_mid': disk_io_div_mid, 'disk_usage_div_mid': disk_usage_div_mid,
                                   'disk_io_view_mid': disk_io_view_mid, 'disk_usage_view_mid': disk_usage_view_mid})
    # Disk IO selection
    view.view_ctx = Mock(disk_stats='io', **{'format_url.return_value': 'an url'})
    view.write_disk_statistics(contents_elt, stats)
    assert mocked_io.call_args_list == [call(contents_elt, 'disk io')]
    assert not mocked_usage.called
    assert contents_elt.findmeld.call_args_list == [call('disk_usage_div_mid'), call('disk_io_view_mid')]
    assert disk_usage_div_mid.replace.call_args_list == [call('')]
    assert disk_io_view_mid.attributes.call_args_list == [call(href='an url')]
    assert not disk_io_div_mid.replace.called
    assert not disk_usage_view_mid.attributes.called
    mocker.resetall()
    contents_elt.reset_all()
    # Disk IO selection
    view.view_ctx.disk_stats = 'usage'
    view.write_disk_statistics(contents_elt, stats)
    assert mocked_usage.call_args_list == [call(contents_elt, 'disk usage')]
    assert not mocked_io.called
    assert contents_elt.findmeld.call_args_list == [call('disk_io_div_mid'), call('disk_usage_view_mid')]
    assert disk_io_div_mid.replace.call_args_list == [call('')]
    assert disk_usage_view_mid.attributes.call_args_list == [call(href='an url')]
    assert not disk_usage_div_mid.replace.called
    assert not disk_io_view_mid.attributes.called


def test_write_cpu_image(mocker, view):
    """ Test the _write_cpu_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    # set context (meant to be set through render)
    view.view_ctx = Mock(cpu_id=0, **{'cpu_id_to_string.return_value': ViewContext.cpu_id_to_string(0)})
    # just test calls to StatisticsPlot
    dummy_cpu_stats = ['#all stats', '#0 stats', '#1 stats']
    dummy_times_stats = [1, 2, 3]
    view._write_cpu_image(dummy_cpu_stats, dummy_times_stats)
    assert mocked_time.call_args_list == [call(dummy_times_stats)]
    assert mocked_plot.call_args_list == [call('CPU #all', '%', '#all stats')]
    assert mocked_export.call_args_list == [call(host_cpu_img)]


def test_write_mem_image(mocker, view):
    """ Test the _write_mem_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    # just test calls to StatisticsPlot
    dummy_mem_stats = ['mem 1', 'mem 2']
    dummy_times_stats = [1, 2, 3]
    view._write_mem_image(dummy_mem_stats, dummy_times_stats)
    assert mocked_time.call_args_list == [call(dummy_times_stats)]
    assert mocked_plot.call_args_list == [call('MEM', '%', dummy_mem_stats)]
    assert mocked_export.call_args_list == [call(host_mem_img)]


def test_write_net_io_image(mocker, view):
    """ Test the _write_net_io_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    # set context (meant to be set through render)
    view.view_ctx = Mock(nic_name='eth0')
    # just test calls to StatisticsPlot
    dummy_io_stats = {'lo': [[1, 2, 3, 4], ['lo recv', 'lo sent']],
                      'eth0': [[2, 3, 4], ['eth0 recv', 'eth0 sent']]}
    view._write_net_io_image(dummy_io_stats)
    assert mocked_time.call_args_list == [call([2, 3, 4])]
    assert mocked_plot.call_args_list == [call('eth0 received', 'kbits/s', 'eth0 recv'),
                                          call('eth0 sent', 'kbits/s', 'eth0 sent')]
    assert mocked_export.call_args_list == [call(host_net_io_img)]


def test_write_disk_image(mocker, view):
    """ Test the _write_disk_image method. """
    mocked_usage = mocker.patch.object(view, '_write_disk_usage_image')
    mocked_io = mocker.patch.object(view, '_write_disk_io_image')
    # set context (meant to be set through render)
    stats = Mock(disk_usage='disk usage', disk_io='disk io')
    # Disk IO selection
    view.view_ctx = Mock(disk_stats='io')
    view._write_disk_image(stats)
    assert mocked_io.call_args_list == [call('disk io')]
    assert not mocked_usage.called
    mocker.resetall()
    # Disk IO selection
    view.view_ctx.disk_stats = 'usage'
    view._write_disk_image(stats)
    assert mocked_usage.call_args_list == [call('disk usage')]
    assert not mocked_io.called


def test_write_disk_io_image(mocker, view):
    """ Test the _write_disk_io_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    # set context (meant to be set through render)
    view.view_ctx = Mock(device='sda')
    # just test calls to StatisticsPlot
    dummy_io_stats = {'sda': [[1, 2, 3, 4], ['sda read', 'sda written']],
                      'sdb': [[2, 3, 4], ['sdb read', 'sdb written']]}
    view._write_disk_io_image(dummy_io_stats)
    assert mocked_time.call_args_list == [call([1, 2, 3, 4])]
    assert mocked_plot.call_args_list == [call('sda read', 'kbits/s', 'sda read'),
                                          call('sda written', 'kbits/s', 'sda written')]
    assert mocked_export.call_args_list == [call(host_disk_io_img)]


def test_write_disk_usage_image(mocker, view):
    """ Test the _write_disk_usage_image method. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    # set context (meant to be set through render)
    view.view_ctx = Mock(partition='/root')
    # just test calls to StatisticsPlot
    dummy_io_stats = {'/': [[1, 2, 3, 4], ['/ percent']],
                      '/root': [[2, 3, 4], ['/root percent']]}
    view._write_disk_usage_image(dummy_io_stats)
    assert mocked_time.call_args_list == [call([2, 3, 4])]
    assert mocked_plot.call_args_list == [call('/root', '%', '/root percent')]
    assert mocked_export.call_args_list == [call(host_disk_usage_img)]
