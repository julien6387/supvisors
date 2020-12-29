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

import sys
import unittest

from unittest.mock import call, patch, Mock

from supvisors.tests.base import DummyHttpContext


class ViewHostAddressTest(unittest.TestCase):
    """ Test case for the viewhostaddress module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        # apply the forced inheritance done in supvisors.plugin
        from supvisors.viewhandler import ViewHandler
        from supervisor.web import StatusView
        StatusView.__bases__ = (ViewHandler,)
        # create the instance to be tested
        from supvisors.viewhostaddress import HostAddressView
        self.view = HostAddressView(DummyHttpContext('ui/hostaddress.html'))

    def test_init(self):
        """ Test the values set at construction. """
        from supvisors.webutils import HOST_ADDRESS_PAGE
        self.assertEqual(HOST_ADDRESS_PAGE, self.view.page_name)

    @patch('supvisors.viewhostaddress.HostAddressView._write_io_image')
    @patch('supvisors.viewhostaddress.HostAddressView._write_mem_image')
    @patch('supvisors.viewhostaddress.HostAddressView._write_cpu_image')
    @patch('supvisors.viewhostaddress.HostAddressView.write_network_statistics')
    @patch('supvisors.viewhostaddress.HostAddressView.write_memory_statistics')
    @patch('supvisors.viewhostaddress.HostAddressView.write_processor_statistics')
    def test_write_contents(self, mocked_processor, mocked_memory, mocked_network,
                            mocked_cpu, mocked_mem, mocked_io):
        """ Test the write_contents method. """
        from supvisors import viewhostaddress
        # set context (meant to be set through render)
        dummy_stats = Mock(cpu='cpu', mem='mem', io='io')
        self.view.view_ctx = Mock(**{'get_address_stats.return_value': dummy_stats})        # replace root structure
        mocked_root = Mock()
        # in first test, HAS_PLOT is False
        viewhostaddress.HAS_PLOT = False
        self.view.write_contents(mocked_root)
        self.assertEqual([call(mocked_root, 'cpu')], mocked_processor.call_args_list)
        self.assertEqual([call(mocked_root, 'mem')], mocked_memory.call_args_list)
        self.assertEqual([call(mocked_root, 'io')], mocked_network.call_args_list)
        self.assertFalse(mocked_cpu.called)
        self.assertFalse(mocked_mem.called)
        self.assertFalse(mocked_io.called)
        # reset mocks
        mocked_processor.reset_mock()
        mocked_memory.reset_mock()
        mocked_network.reset_mock()
        # in second test, HAS_PLOT is True
        viewhostaddress.HAS_PLOT = True
        self.view.write_contents(mocked_root)
        self.assertEqual([call(mocked_root, 'cpu')], mocked_processor.call_args_list)
        self.assertEqual([call(mocked_root, 'mem')], mocked_memory.call_args_list)
        self.assertEqual([call(mocked_root, 'io')], mocked_network.call_args_list)
        self.assertEqual([call('cpu')], mocked_cpu.call_args_list)
        self.assertEqual([call('mem')], mocked_mem.call_args_list)
        self.assertEqual([call('io')], mocked_io.call_args_list)

    def test_write_processor_single_title(self):
        """ Test the _write_processor_single_title method. """
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html',
                                     'cpu_id_to_string.return_value': '1'})        # replace root structure
        mocked_title_mid = Mock(attrib={})
        mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
        # in first call, elt is not the selected element
        self.view._write_processor_single_title(mocked_tr, 1, 0)
        self.assertEqual([call('cpunum_a_mid')], mocked_tr.findmeld.call_args_list)
        self.assertDictEqual({}, mocked_title_mid.attrib)
        self.assertEqual([call(href='http://addr:port/index.html')], mocked_title_mid.attributes.call_args_list)
        self.assertEqual([call('cpu#1')], mocked_title_mid.content.call_args_list)
        mocked_tr.findmeld.reset_mock()
        mocked_title_mid.attributes.reset_mock()
        # in first call, elt is the selected element
        self.view._write_processor_single_title(mocked_tr, 1, 1)
        self.assertEqual([call('cpunum_a_mid')], mocked_tr.findmeld.call_args_list)
        self.assertDictEqual({'class': 'button off active'}, mocked_title_mid.attrib)
        self.assertFalse(mocked_title_mid.attributes.called)
        self.assertEqual([call('cpu#1')], mocked_title_mid.content.call_args_list)

    @patch('supvisors.viewhostaddress.HostAddressView._write_common_statistics')
    def test_write_processor_single_statistics(self, mocked_common):
        """ Test the _write_processor_single_statistics method. """
        # replace root element
        mocked_root = Mock()
        # test method call
        self.view._write_processor_single_statistics(mocked_root, [1.523, 2.456])
        self.assertEqual([call(mocked_root, [1.523, 2.456], 'cpuval_td_mid', 'cpuavg_td_mid',
                               'cpuslope_td_mid', 'cpudev_td_mid')],
                         mocked_common.call_args_list)

    @patch('supvisors.viewhostaddress.HostAddressView._write_processor_single_statistics')
    @patch('supvisors.viewhostaddress.HostAddressView._write_processor_single_title')
    def test_write_processor_statistics(self, mocked_title, mocked_stats):
        """ Test the write_processor_statistics method. """
        from supvisors.viewcontext import CPU
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(parameters={CPU: 1})
        # build root structure
        mocked_trs = [Mock(attrib={}) for _ in range(2)]
        mocked_mid = Mock(**{'repeat.return_value': [(mocked_trs[0], 'cpu stats 0'),
                                                     (mocked_trs[1], 'cpu stats 1')]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test call
        self.view.write_processor_statistics(mocked_root, [])
        self.assertEqual([call(mocked_trs[0], 1, 0), call(mocked_trs[1], 1, 1)],
                         mocked_title.call_args_list)
        self.assertEqual([call(mocked_trs[0], 'cpu stats 0'), call(mocked_trs[1], 'cpu stats 1')],
                         mocked_stats.call_args_list)
        self.assertDictEqual({'class': 'brightened'}, mocked_trs[0].attrib)
        self.assertDictEqual({'class': 'shaded'}, mocked_trs[1].attrib)

    @patch('supvisors.viewhostaddress.HostAddressView._write_common_statistics')
    def test_write_memory_statistics(self, mocked_common):
        """ Test the write_memory_statistics method. """
        # replace root element
        mocked_root = Mock()
        # test method call
        self.view.write_memory_statistics(mocked_root, [1.523, 2.456])
        self.assertEqual([call(mocked_root, [1.523, 2.456], 'memval_td_mid', 'memavg_td_mid',
                               'memslope_td_mid', 'memdev_td_mid')],
                         mocked_common.call_args_list)

    def test_write_network_single_title(self):
        """ Test the _write_network_single_title method. """
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(**{'format_url.return_value': 'http://addr:port/index.html'})
        # replace root structure
        mocked_href_mid = Mock(attrib={})
        mocked_title_mid = Mock(attrib={}, **{'findmeld.return_value': mocked_href_mid})
        mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
        # in first call, elt is not the first line (rowspan False)
        self.view._write_network_single_title(mocked_tr, 'eth0', 'lo', False, True)
        self.assertEqual([call('intf_td_mid')], mocked_tr.findmeld.call_args_list)
        self.assertDictEqual({}, mocked_title_mid.attrib)
        self.assertFalse(mocked_title_mid.findmeld.called)
        self.assertDictEqual({}, mocked_href_mid.attrib)
        self.assertEqual([call('')], mocked_title_mid.replace.call_args_list)
        mocked_tr.findmeld.reset_mock()
        mocked_title_mid.replace.reset_mock()
        # in second call, elt is the first line (rowspan True), shaded and is not the selected interface
        self.view._write_network_single_title(mocked_tr, 'eth0', 'lo', True, True)
        self.assertEqual([call('intf_td_mid')], mocked_tr.findmeld.call_args_list)
        self.assertDictEqual({'class': 'shaded', 'rowspan': '2'}, mocked_title_mid.attrib)
        self.assertEqual([call('intf_a_mid')], mocked_title_mid.findmeld.call_args_list)
        self.assertDictEqual({}, mocked_href_mid.attrib)
        self.assertEqual([call(href='http://addr:port/index.html')], mocked_href_mid.attributes.call_args_list)
        self.assertFalse(mocked_title_mid.replace.called)
        mocked_tr.findmeld.reset_mock()
        mocked_title_mid.findmeld.reset_mock()
        mocked_href_mid.attributes.reset_mock()
        # in third call, elt is the first line (rowspan True), not shaded and is the selected interface
        self.view._write_network_single_title(mocked_tr, 'lo', 'lo', True, False)
        self.assertEqual([call('intf_td_mid')], mocked_tr.findmeld.call_args_list)
        self.assertDictEqual({'class': 'brightened', 'rowspan': '2'}, mocked_title_mid.attrib)
        self.assertEqual([call('intf_a_mid')], mocked_title_mid.findmeld.call_args_list)
        self.assertDictEqual({'class': 'button off active'}, mocked_href_mid.attrib)
        self.assertFalse(mocked_href_mid.attributes.called)
        self.assertFalse(mocked_title_mid.replace.called)

    @patch('supvisors.viewhostaddress.HostAddressView._write_common_statistics')
    def test_write_network_single_statistics(self, mocked_common):
        """ Test the _write_network_single_statistics method. """
        # replace root structure
        mocked_title_mid = Mock()
        mocked_tr = Mock(**{'findmeld.return_value': mocked_title_mid})
        # in first call, test no rate, slope and standard deviation
        self.view._write_network_single_statistics(mocked_tr, [1.523, 2.456], False)
        self.assertEqual([call('intfrxtx_td_mid')], mocked_tr.findmeld.call_args_list)
        self.assertEqual([call('Tx')], mocked_title_mid.content.call_args_list)
        self.assertEqual([call(mocked_tr, [1.523, 2.456], 'intfval_td_mid', 'intfavg_td_mid',
                               'intfslope_td_mid', 'intfdev_td_mid')],
                         mocked_common.call_args_list)
        mocked_tr.reset_mock()
        mocked_title_mid.content.reset_mock()
        mocked_common.reset_mock()
        # in second call, test no rate, slope and standard deviation
        self.view._write_network_single_statistics(mocked_tr, [1.523, 2.456], True)
        self.assertEqual([call('intfrxtx_td_mid')], mocked_tr.findmeld.call_args_list)
        self.assertEqual([call('Rx')], mocked_title_mid.content.call_args_list)
        self.assertEqual([call(mocked_tr, [1.523, 2.456], 'intfval_td_mid', 'intfavg_td_mid',
                               'intfslope_td_mid', 'intfdev_td_mid')],
                         mocked_common.call_args_list)

    @patch('supvisors.viewhostaddress.HostAddressView._write_network_single_statistics')
    @patch('supvisors.viewhostaddress.HostAddressView._write_network_single_title')
    def test_write_network_statistics(self, mocked_title, mocked_stats):
        """ Test the write_network_statistics method. """
        from supvisors.viewcontext import INTF
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(parameters={INTF: 'eth0'})
        # build root structure
        mocked_trs = [Mock(attrib={}) for _ in range(4)]
        mocked_mid = Mock(**{'repeat.return_value': [(mocked_trs[0], ('lo', 'lo recv')),
                                                     (mocked_trs[1], ('lo', 'lo sent')),
                                                     (mocked_trs[2], ('eth0', 'eth0 recv')),
                                                     (mocked_trs[3], ('eth0', 'eth0 sent'))]})
        mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
        # test method with dummy stats
        dummy_stats = {'lo': ['lo recv', 'lo sent'], 'eth0': ['eth0 recv', 'eth0 sent']}
        self.view.write_network_statistics(mocked_root, dummy_stats)
        # check calls
        self.assertEqual([call('intf_tr_mid')], mocked_root.findmeld.call_args_list)
        self.assertEqual([call([('lo', 'lo recv'), ('lo', 'lo sent'),
                                ('eth0', 'eth0 recv'), ('eth0', 'eth0 sent')])],
                         mocked_mid.repeat.call_args_list)
        self.assertEqual('brightened', mocked_trs[0].attrib['class'])
        self.assertEqual('brightened', mocked_trs[1].attrib['class'])
        self.assertEqual('shaded', mocked_trs[2].attrib['class'])
        self.assertEqual('shaded', mocked_trs[3].attrib['class'])
        self.assertEqual([call(mocked_trs[0], 'eth0', 'lo', True, False),
                          call(mocked_trs[1], 'eth0', 'lo', False, False),
                          call(mocked_trs[2], 'eth0', 'eth0', True, True),
                          call(mocked_trs[3], 'eth0', 'eth0', False, True)],
                         mocked_title.call_args_list)
        self.assertEqual([call(mocked_trs[0], 'lo recv', True),
                          call(mocked_trs[1], 'lo sent', False),
                          call(mocked_trs[2], 'eth0 recv', True),
                          call(mocked_trs[3], 'eth0 sent', False)],
                         mocked_stats.call_args_list)

    @patch('supvisors.viewhostaddress.get_stats', side_effect=[(10.231, None, (None, 2), None),
                                                               (8.999, 2, (-1.1, 4), 5.72)])
    @patch('supvisors.viewhostaddress.HostAddressView.set_slope_class')
    def test_write_common_statistics(self, mocked_class, mocked_stats):
        """ Test the _write_common_statistics method. """
        # replace root structure
        mocked_val_mid = Mock()
        mocked_avg_mid = Mock()
        mocked_slope_mid = Mock()
        mocked_dev_mid = Mock()
        mocked_tr = Mock(**{'findmeld.side_effect': [mocked_val_mid, mocked_avg_mid,
                                                     mocked_val_mid, mocked_avg_mid,
                                                     mocked_slope_mid, mocked_dev_mid]})
        # in first call, test empty stats
        self.view._write_common_statistics(mocked_tr, [], 'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
        self.assertFalse(mocked_tr.findmeld.called)
        self.assertFalse(mocked_stats.called)
        self.assertFalse(mocked_class.called)
        self.assertFalse(mocked_val_mid.called)
        self.assertFalse(mocked_avg_mid.called)
        self.assertFalse(mocked_slope_mid.called)
        self.assertFalse(mocked_dev_mid.called)
        # in second call, test no rate, slope and standard deviation
        self.view._write_common_statistics(mocked_tr, [1.523, 2.456], 'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
        self.assertEqual([call('val_mid'), call('avg_mid')], mocked_tr.findmeld.call_args_list)
        self.assertEqual([call([1.523, 2.456])], mocked_stats.call_args_list)
        self.assertFalse(mocked_class.called)
        self.assertEqual([call('2.46')], mocked_val_mid.content.call_args_list)
        self.assertEqual([call('10.23')], mocked_avg_mid.content.call_args_list)
        self.assertFalse(mocked_slope_mid.called)
        self.assertFalse(mocked_dev_mid.called)
        mocked_stats.reset_mock()
        mocked_val_mid.content.reset_mock()
        mocked_avg_mid.content.reset_mock()
        # in third call, test no rate, slope and standard deviation
        self.view._write_common_statistics(mocked_tr, [1.523, 2.456], 'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
        self.assertEqual([call([1.523, 2.456])], mocked_stats.call_args_list)
        self.assertEqual([call(mocked_val_mid, 2)], mocked_class.call_args_list)
        self.assertEqual([call('val_mid'), call('avg_mid'),
                          call('val_mid'), call('avg_mid'), call('slope_mid'), call('dev_mid')],
                         mocked_tr.findmeld.call_args_list)
        self.assertEqual([call('2.46')], mocked_val_mid.content.call_args_list)
        self.assertEqual([call('9.00')], mocked_avg_mid.content.call_args_list)
        self.assertEqual([call('-1.10')], mocked_slope_mid.content.call_args_list)
        self.assertEqual([call('5.72')], mocked_dev_mid.content.call_args_list)

    @patch('supvisors.plot.StatisticsPlot.export_image')
    @patch('supvisors.plot.StatisticsPlot.add_plot')
    def test_write_cpu_image(self, mocked_add, mocked_export):
        """ Test the _write_cpu_image method. """
        from supvisors.viewcontext import ViewContext, CPU
        from supvisors.viewimage import address_cpu_img
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(parameters={CPU: 0},
                             **{'cpu_id_to_string.return_value': ViewContext.cpu_id_to_string(0)})
        # just test calls to StatisticsPlot
        dummy_stats = ['#all stats', '#0 stats', '#1 stats']
        self.view._write_cpu_image(dummy_stats)
        self.assertEqual([call('CPU #all', '%', '#all stats')], mocked_add.call_args_list)
        self.assertEqual([call(address_cpu_img)], mocked_export.call_args_list)

    @patch('supvisors.plot.StatisticsPlot.export_image')
    @patch('supvisors.plot.StatisticsPlot.add_plot')
    def test_write_mem_image(self, mocked_add, mocked_export):
        """ Test the _write_mem_image method. """
        from supvisors.viewimage import address_mem_img
        # just test calls to StatisticsPlot
        dummy_stats = ['mem 1', 'mem 2']
        self.view._write_mem_image(dummy_stats)
        self.assertEqual([call('MEM', '%', dummy_stats)], mocked_add.call_args_list)
        self.assertEqual([call(address_mem_img)], mocked_export.call_args_list)

    @patch('supvisors.plot.StatisticsPlot.export_image')
    @patch('supvisors.plot.StatisticsPlot.add_plot')
    def test_write_io_image(self, mocked_add, mocked_export):
        """ Test the _write_io_image method. """
        from supvisors.viewcontext import INTF
        from supvisors.viewimage import address_io_img
        # set context (meant to be set through render)
        self.view.view_ctx = Mock(parameters={INTF: 'eth0'})
        # just test calls to StatisticsPlot
        dummy_stats = {'lo': ['lo recv', 'lo sent'], 'eth0': ['eth0 recv', 'eth0 sent']}
        self.view._write_io_image(dummy_stats)
        self.assertEqual([call('eth0 recv', 'kbits/s', 'eth0 recv'),
                          call('eth0 sent', 'kbits/s', 'eth0 sent')],
                         mocked_add.call_args_list)
        self.assertEqual([call(address_io_img)], mocked_export.call_args_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
