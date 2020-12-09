#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import multiprocessing
import unittest
import sys

from supvisors.tests.base import MockedSupvisors, CompatTestCase


class StatisticsTest(CompatTestCase):
    """ Test case for the functions of the statscompiler module. """

    def test_cpu_statistics(self):
        """ Test the CPU statistics between 2 dates. """
        from supvisors.statscompiler import cpu_statistics
        # take 2 spaced instant cpu statistics
        ref_stats = [(83.31, 305.4)] * (multiprocessing.cpu_count() + 1)
        last_stats = [(83.32, 306.4)] * (multiprocessing.cpu_count() + 1)
        stats = cpu_statistics(last_stats, ref_stats)
        # test number of results (number of cores + average)
        self.assertEqual(multiprocessing.cpu_count() + 1, len(stats))
        # test bounds (percent)
        for cpu in stats:
            self.assertIs(float, type(cpu))
            self.assertGreaterEqual(cpu, 0)
            self.assertLessEqual(cpu, 100)

    # average cannot be tested as floating point operations have already caused a drift

    def test_cpu_total_work(self):
        """ Test the CPU total work between 2 dates. """
        from supvisors.statscompiler import cpu_total_work
        # take 2 instant cpu statistics
        ref_stats = [(83.31, 305.4)] * 2
        last_stats = [(83.41, 306.3)] * 2
        total_work = cpu_total_work(last_stats, ref_stats)
        # total work is the sum of jiffies spent on cpu all
        self.assertAlmostEqual(1, total_work, 1)

    def test_io_statistics(self):
        """ Test the I/O statistics between 2 dates. """
        from supvisors.statscompiler import io_statistics
        # take 2 instant cpu statistics
        ref_stats = {'eth0': (2000, 200), 'lo': (5000, 5000)}
        last_stats = {'eth0': (2896, 328), 'lo': (6024, 6024)}
        stats = io_statistics(last_stats, ref_stats, 1)
        # test keys
        self.assertItemsEqual(ref_stats.keys(), stats.keys())
        self.assertItemsEqual(last_stats.keys(), stats.keys())
        # test that values
        self.assertDictEqual({'lo': (8, 8), 'eth0': (7, 1)}, stats)

    def test_cpu_process_statistics(self):
        """ Test the CPU of the process between 2 dates. """
        from supvisors.statscompiler import cpu_process_statistics
        stats = cpu_process_statistics(50, 20, 100)
        self.assertIs(float, type(stats))
        self.assertEqual(30, stats)

    def test_statistics(self):
        """ Test the global statistics between 2 dates. """
        from supvisors.statscompiler import statistics
        ref_stats = (1000, [(25, 400), (25, 125), (15, 150)], 65, {'eth0': (2000, 200), 'lo': (5000, 5000)},
                     {'myself': (26088, (0.15, 1.85))})
        last_stats = (1002, [(45, 700), (50, 225), (40, 250)], 67.7, {'eth0': (2768, 456), 'lo': (6024, 6024)},
                      {'myself': (26088, (1.75, 1.9))})
        stats = statistics(last_stats, ref_stats)
        # check result
        self.assertEqual(5, len(stats))
        date, cpu_stats, mem_stats, io_stats, proc_stats = stats
        # check date
        self.assertEqual(1002, date)
        # check cpu
        self.assertListEqual([6.25, 20.0, 20.0], cpu_stats)
        # check memory
        self.assertEqual(67.7, mem_stats)
        # check io
        self.assertDictEqual({'lo': (4, 4), 'eth0': (3, 1)}, io_stats)
        # check process stats
        self.assertDictEqual({('myself', 26088): (0.5, 1.9)}, proc_stats)


class StatisticsInstanceTest(CompatTestCase):
    """ Test case for the StatisticsInstance class of the statscompiler module. """

    def test_create(self):
        """ Test the initialization of an instance. """
        from supvisors.statscompiler import StatisticsInstance
        instance = StatisticsInstance(17, 10)
        # check attributes
        self.assertEqual(3, instance.period)
        self.assertEqual(10, instance.depth)
        self.assertEqual(-1, instance.counter)
        self.assertIsNone(instance.ref_stats)
        self.assertIs(list, type(instance.cpu))
        self.assertFalse(instance.cpu)
        self.assertIs(list, type(instance.mem))
        self.assertFalse(instance.mem)
        self.assertIs(dict, type(instance.io))
        self.assertFalse(instance.io)
        self.assertIs(dict, type(instance.proc))
        self.assertFalse(instance.proc)

    def test_clear(self):
        """ Test the clearance of an instance. """
        from supvisors.statscompiler import StatisticsInstance
        instance = StatisticsInstance(17, 10)
        # change values
        instance.counter = 28
        instance.ref_stats = ('dummy', 0)
        instance.cpu = [13.2, 14.8]
        instance.mem = [56.4, 71.3, 68.9]
        instance.io = {'eth0': (123465, 654321), 'lo': (321, 321)}
        instance.proc = {('myself', 5888): (25.0, 12.5)}
        # check clearance
        instance.clear()
        self.assertEqual(3, instance.period)
        self.assertEqual(10, instance.depth)
        self.assertEqual(-1, instance.counter)
        self.assertIsNone(instance.ref_stats)
        self.assertIs(list, type(instance.cpu))
        self.assertFalse(instance.cpu)
        self.assertIs(list, type(instance.mem))
        self.assertFalse(instance.mem)
        self.assertIs(dict, type(instance.io))
        self.assertFalse(instance.io)
        self.assertIs(dict, type(instance.proc))
        self.assertFalse(instance.proc)

    def test_find_process_stats(self):
        """ Test the search method for process statistics. """
        from supvisors.statscompiler import StatisticsInstance
        instance = StatisticsInstance(17, 10)
        # change values
        instance.proc = {('the_other', 1234): (1.5, 2.4), ('myself', 5888): (25.0, 12.5)}
        # test find method with wrong argument
        self.assertIsNone(instance.find_process_stats('someone'))
        # test find method with correct argument
        stats = instance.find_process_stats('myself')
        self.assertTupleEqual((25.0, 12.5), stats)

    def test_trunc_depth(self):
        """ Test the history depth. """
        from supvisors.statscompiler import StatisticsInstance
        instance = StatisticsInstance(12, 5)
        # test that the truc_depth method does nothing when less than 5 elements in list
        test_list = [1, 2, 3, 4]
        instance.trunc_depth(test_list)
        self.assertListEqual([1, 2, 3, 4], test_list)
        # test that the truc_depth method keeps only the last 5 elements in list
        test_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        instance.trunc_depth(test_list)
        self.assertListEqual([6, 7, 8, 9, 10], test_list)

    def test_push_statistics(self):
        """ Test the storage of the instant statistics. """
        from supvisors.statscompiler import StatisticsInstance
        # testing with period 12 and history depth 2
        instance = StatisticsInstance(12, 2)
        # push first set of measures
        stats1 = (8.5, [(25, 400), (25, 125), (15, 150), (40, 400), (20, 200)],
                  76.1, {'eth0': (1024, 2000), 'lo': (500, 500)},
                  {'myself': (118612, (0.15, 1.85)), 'other1': (7754, (0.15, 1.85)), 'other2': (826, (0.15, 1.85))})
        instance.push_statistics(stats1)
        # check evolution of instance
        self.assertEqual(0, instance.counter)
        self.assertEqual(5, len(instance.cpu))
        for cpu in instance.cpu:
            self.assertFalse(cpu)
        self.assertFalse(instance.mem)
        self.assertItemsEqual(['eth0', 'lo'], instance.io.keys())
        for recv, sent in instance.io.values():
            self.assertIs(list, type(recv))
            self.assertFalse(recv)
            self.assertIs(list, type(sent))
            self.assertFalse(sent)
        self.assertItemsEqual([('myself', 118612), ('other1', 7754), ('other2', 826)], instance.proc.keys())
        for cpu_list, mem_list in instance.proc.values():
            self.assertIs(list, type(cpu_list))
            self.assertFalse(cpu_list)
            self.assertIs(list, type(mem_list))
            self.assertFalse(mem_list)
        self.assertIs(stats1, instance.ref_stats)
        # push second set of measures
        stats2 = (18.52, [(30, 600), (40, 150), (30, 200), (41, 550), (20, 300)],
                  76.2, {'eth0': (1250, 2200), 'lo': (620, 620)},
                  {'myself': (118612, (0.16, 1.84)), 'other2': (826, (0.16, 1.84))})
        instance.push_statistics(stats2)
        # counter is based a theoretical period of 5 seconds
        # this update is not taken into account
        # check evolution of instance
        self.assertEqual(1, instance.counter)
        self.assertEqual(5, len(instance.cpu))
        for cpu in instance.cpu:
            self.assertFalse(cpu)
        self.assertFalse(instance.mem)
        self.assertItemsEqual(['eth0', 'lo'], instance.io.keys())
        for recv, sent in instance.io.values():
            self.assertIs(list, type(recv))
            self.assertFalse(recv)
            self.assertIs(list, type(sent))
            self.assertFalse(sent)
        self.assertItemsEqual([('myself', 118612), ('other1', 7754), ('other2', 826)], instance.proc.keys())
        for cpu_list, mem_list in instance.proc.values():
            self.assertIs(list, type(cpu_list))
            self.assertFalse(cpu_list)
            self.assertIs(list, type(mem_list))
            self.assertFalse(mem_list)
        self.assertIs(stats1, instance.ref_stats)
        # push third set of measures
        stats3 = (28.5, [(45, 700), (50, 225), (40, 250), (42, 598), (20, 400)],
                  76.1, {'eth0': (2048, 2512), 'lo': (756, 756)},
                  {'myself': (118612, (1.75, 1.9)), 'other1': (8865, (1.75, 1.9))})
        instance.push_statistics(stats3)
        # this update is taken into account
        # check evolution of instance
        self.assertEqual(2, instance.counter)
        self.assertListEqual([[6.25], [20.0], [20.0], [1.0], [0.0]], instance.cpu)
        self.assertListEqual([76.1], instance.mem)
        self.assertDictEqual({'eth0': ([0.4], [0.2]), 'lo': ([0.1], [0.1])}, instance.io)
        self.assertDictEqual({('myself', 118612): ([0.5], [1.9])}, instance.proc)
        self.assertIs(stats3, instance.ref_stats)
        # push fourth set of measures (reuse stats2)
        instance.push_statistics(stats2)
        # again,this update is not taken into account
        self.assertEqual(3, instance.counter)
        self.assertIs(stats3, instance.ref_stats)
        # push fifth set of measures
        stats5 = (38.5, [(80, 985), (89, 386), (48, 292), (42, 635), (32, 468)],
                  75.9, {'eth0': (3072, 2768), 'lo': (1780, 1780)},
                  {'myself': (118612, (11.75, 1.87)), 'other1': (8865, (11.75, 1.87))})
        instance.push_statistics(stats5)
        # this update is taken into account
        # check evolution of instance
        self.assertEqual(4, instance.counter)
        self.assertListEqual([[6.25, 10.9375], [20.0, 19.5], [20.0, 16.0], [1.0, 0.0], [0.0, 15.0]],
                             instance.cpu)
        self.assertListEqual([76.1, 75.9], instance.mem)
        self.assertDictEqual({'eth0': ([0.4, 0.8], [0.2, 0.2]), 'lo': ([0.1, 0.8], [0.1, 0.8])},
                             instance.io)
        self.assertEqual({('myself', 118612): ([0.5, 3.125], [1.9, 1.87]),
                          ('other1', 8865): ([3.125], [1.87])},
                         instance.proc)
        self.assertIs(stats5, instance.ref_stats)
        # push sixth set of measures (reuse stats2)
        instance.push_statistics(stats2)
        # this update is not taken into account
        # check evolution of instance
        self.assertEqual(5, instance.counter)
        self.assertIs(stats5, instance.ref_stats)
        # push seventh set of measures
        stats7 = (48.5, [(84, 1061), (92, 413), (48, 480), (45, 832), (40, 1100)],
                  74.7, {'eth0': (3584, 3792), 'lo': (1812, 1812)},
                  {'myself': (118612, (40.75, 2.34)), 'other1': (8865, (40.75, 2.34))})
        instance.push_statistics(stats7)
        # this update is taken into account
        # check evolution of instance. max depth is reached so lists roll
        self.assertEqual(6, instance.counter)
        self.assertListEqual([[10.9375, 5.0], [19.5, 10.0], [16.0, 0.0], [0.0, 1.5], [15.0, 1.25]],
                             instance.cpu)
        self.assertListEqual([75.9, 74.7], instance.mem)
        self.assertDictEqual({'eth0': ([0.8, 0.4], [0.2, 0.8]), 'lo': ([0.8, 0.025], [0.8, 0.025])},
                             instance.io)
        self.assertEqual({('myself', 118612): ([3.125, 36.25], [1.87, 2.34]),
                          ('other1', 8865): ([3.125, 36.25], [1.87, 2.34])}, instance.proc)
        self.assertIs(stats7, instance.ref_stats)


class StatisticsCompilerTest(CompatTestCase):
    """ Test case for the StatisticsCompiler class of the statscompiler module. """

    def setUp(self):
        """ Create a dummy supvisors. """
        self.supvisors = MockedSupvisors()

    def test_create(self):
        """ Test the initialization for statistics of all addresses. """
        from supvisors.statscompiler import StatisticsCompiler, StatisticsInstance
        compiler = StatisticsCompiler(self.supvisors)
        # check compiler contents at initialisation
        self.assertItemsEqual(self.supvisors.address_mapper.addresses, compiler.data.keys())
        for period_instance in compiler.data.values():
            self.assertItemsEqual(self.supvisors.options.stats_periods, period_instance.keys())
            for period, instance in period_instance.items():
                self.assertIs(StatisticsInstance, type(instance))
                self.assertEqual(period / 5, instance.period)
                self.assertEqual(self.supvisors.options.stats_histo, instance.depth)

    def test_clear(self):
        """ Test the clearance for statistics of all addresses. """
        from supvisors.statscompiler import StatisticsCompiler
        compiler = StatisticsCompiler(self.supvisors)
        # set data to a given address
        for address, period_instance in compiler.data.items():
            for period, instance in period_instance.items():
                instance.counter = 28
                instance.ref_stats = ('dummy', 0)
                instance.cpu = [13.2, 14.8]
                instance.mem = [56.4, 71.3, 68.9]
                instance.io = {'eth0': (123465, 654321), 'lo': (321, 321)}
                instance.proc = {('myself', 5888): (25.0, 12.5)}
        # check clearance of instance
        compiler.clear('10.0.0.2')
        for address, period_instance in compiler.data.items():
            if address == '10.0.0.2':
                for period, instance in period_instance.items():
                    self.assertEqual(period / 5, instance.period)
                    self.assertEqual(10, instance.depth)
                    self.assertEqual(-1, instance.counter)
                    self.assertIsNone(instance.ref_stats)
                    self.assertIs(list, type(instance.cpu))
                    self.assertFalse(instance.cpu)
                    self.assertIs(list, type(instance.mem))
                    self.assertFalse(instance.mem)
                    self.assertIs(dict, type(instance.io))
                    self.assertFalse(instance.io)
                    self.assertIs(dict, type(instance.proc))
                    self.assertFalse(instance.proc)
            else:
                for period, instance in period_instance.items():
                    self.assertEqual(period / 5, instance.period)
                    self.assertEqual(10, instance.depth)
                    self.assertEqual(28, instance.counter)
                    self.assertTupleEqual(('dummy', 0), instance.ref_stats)
                    self.assertListEqual([13.2, 14.8], instance.cpu)
                    self.assertListEqual([56.4, 71.3, 68.9], instance.mem)
                    self.assertDictEqual({'eth0': (123465, 654321), 'lo': (321, 321)}, instance.io)
                    self.assertDictEqual({('myself', 5888): (25.0, 12.5)}, instance.proc)

    def test_push_statistics(self):
        """ Test the storage of the instant statistics of an address. """
        from supvisors.statscompiler import StatisticsCompiler
        compiler = StatisticsCompiler(self.supvisors)
        # push statistics to a given address
        stats1 = (8.5, [(25, 400), (25, 125), (15, 150), (40, 400), (20, 200)],
                  76.1, {'eth0': (1024, 2000), 'lo': (500, 500)}, {'myself': (118612, (0.15, 1.85))})
        compiler.push_statistics('10.0.0.2', stats1)
        # check compiler contents
        for address, period_instance in compiler.data.items():
            if address == '10.0.0.2':
                for period, instance in period_instance.items():
                    self.assertEqual(0, instance.counter)
                    self.assertIs(stats1, instance.ref_stats)
            else:
                for period, instance in period_instance.items():
                    self.assertEqual(-1, instance.counter)
                    self.assertIsNone(instance.ref_stats)
        # push statistics to a given address
        stats2 = (28.5, [(45, 700), (50, 225), (40, 250), (42, 598), (20, 400)],
                  76.1, {'eth0': (2048, 2512), 'lo': (756, 756)}, {'myself': (118612, (1.75, 1.9))})
        compiler.push_statistics('10.0.0.2', stats2)
        # check compiler contents
        for address, period_instance in compiler.data.items():
            if address == '10.0.0.2':
                for period, instance in period_instance.items():
                    self.assertEqual(1, instance.counter)
                    if period == 5:
                        self.assertIs(stats2, instance.ref_stats)
                    else:
                        self.assertIs(stats1, instance.ref_stats)
            else:
                for period, instance in period_instance.items():
                    self.assertEqual(-1, instance.counter)
                    self.assertIsNone(instance.ref_stats)
        # push statistics to a given address
        stats3 = (38.5, [(80, 985), (89, 386), (48, 292), (42, 635), (32, 468)],
                  75.9, {'eth0': (3072, 2768), 'lo': (1780, 1780)}, {'myself': (118612, (11.75, 1.87))})
        compiler.push_statistics('10.0.0.2', stats3)
        # check compiler contents
        for address, period_instance in compiler.data.items():
            if address == '10.0.0.2':
                for period, instance in period_instance.items():
                    self.assertEqual(2, instance.counter)
                    if period == 5:
                        self.assertIs(stats3, instance.ref_stats)
                    else:
                        self.assertIs(stats1, instance.ref_stats)
            else:
                for period, instance in period_instance.items():
                    self.assertEqual(-1, instance.counter)
                    self.assertIsNone(instance.ref_stats)
        # push statistics to a given address
        stats4 = (48.5, [(84, 1061), (92, 413), (48, 480), (45, 832), (40, 1100)],
                  74.7, {'eth0': (3584, 3792), 'lo': (1812, 1812)}, {'myself': (118612, (40.75, 2.34))})
        compiler.push_statistics('10.0.0.2', stats4)
        # check compiler contents
        for address, period_instance in compiler.data.items():
            if address == '10.0.0.2':
                for period, instance in period_instance.items():
                    self.assertEqual(3, instance.counter)
                    if period in [5, 15]:
                        self.assertIs(stats4, instance.ref_stats)
                    else:
                        self.assertIs(stats1, instance.ref_stats)
            else:
                for period, instance in period_instance.items():
                    self.assertEqual(-1, instance.counter)
                    self.assertIsNone(instance.ref_stats)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
