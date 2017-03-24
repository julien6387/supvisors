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

import sys
import unittest

from supvisors.tests.base import DummySupvisors


class StatisticsTest(unittest.TestCase):
    """ Test case for the functions of the statistics module. """

    def test_instant_cpu_statistics(self):
        """ Test the instant CPU statistics. """
        import multiprocessing
        from supvisors.statistics import instant_cpu_statistics
        stats = instant_cpu_statistics()
        # test number of results (number of cores + average)
        self.assertEqual(multiprocessing.cpu_count() + 1, len(stats))
        # test average value
        total_work = total_idle = 0
        for cpu in stats[1:]:
            self.assertEqual(2, len(cpu))
            work, idle = cpu
            total_work += work
            total_idle += idle
        self.assertAlmostEqual(stats[0][0], total_work / multiprocessing.cpu_count())
        self.assertAlmostEqual(stats[0][1], total_idle / multiprocessing.cpu_count())

    def test_cpu_statistics(self):
        """ Test the CPU statistics between 2 dates. """
        import multiprocessing, time
        from supvisors.statistics import instant_cpu_statistics, cpu_statistics
        # take 2 spaced instant cpu statistics
        ref_stats = instant_cpu_statistics()
        time.sleep(1)
        last_stats = instant_cpu_statistics()
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
        import time
        from supvisors.statistics import instant_cpu_statistics, cpu_total_work
        # take 2 spaced instant cpu statistics
        ref_stats = instant_cpu_statistics()
        time.sleep(1)
        last_stats = instant_cpu_statistics()
        total_work = cpu_total_work(last_stats, ref_stats)
        # total work should be quite close to sleeping time
        self.assertAlmostEqual(1, total_work, 1)

    def test_instant_memory_statistics(self):
        """ Test the instant memory statistics. """
        from supvisors.statistics import instant_memory_statistics
        stats = instant_memory_statistics()
        # test bounds (percent)
        self.assertIs(float, type(stats))
        self.assertGreaterEqual(stats, 0)
        self.assertLessEqual(stats, 100)

    def test_instant_io_statistics(self):
        """ Test the instant I/O statistics. """
        from supvisors.statistics import instant_io_statistics
        stats = instant_io_statistics()
        # test interface names
        with open('/proc/net/dev') as netfile:
            # two first lines are title
            contents = netfile.readlines()[2:]
        interfaces = [intf.strip().split(':')[0] for intf in contents]
        self.assertItemsEqual(interfaces, stats.keys())
        self.assertIn('lo', stats.keys())
        # test that values are pairs
        for intf, bytes in stats.items():
            self.assertEqual(2, len(bytes))
            for value in bytes:
                self.assertIs(int, type(value))
        # for loopback address, recv bytes equals sent bytes
        self.assertEqual(stats['lo'][0], stats['lo'][1])

    def test_io_statistics(self):
        """ Test the I/O statistics between 2 dates. """
        import time
        from supvisors.statistics import instant_io_statistics, io_statistics
        # take 2 spaced instant cpu statistics
        ref_stats = instant_io_statistics()
        time.sleep(1)
        last_stats = instant_io_statistics()
        stats = io_statistics(last_stats, ref_stats, 1)
        # test keys
        self.assertListEqual(ref_stats.keys(), stats.keys())
        self.assertListEqual(last_stats.keys(), stats.keys())
        # test that values are pairs
        for intf, bytes in stats.items():
            self.assertEqual(2, len(bytes))
            for value in bytes:
                self.assertIs(int, type(value))
 
    def test_instant_process_statistics(self):
        """ Test the instant process statistics. """
        import os
        from supvisors.statistics import instant_process_statistics
        # check with existing PID
        work, memory = instant_process_statistics(os.getpid())
        # test that a pair is returned with values in [0;100]
        # test cpu value
        self.assertIs(float, type(work))
        self.assertGreaterEqual(work, 0)
        self.assertLessEqual(work, 100)
        # test mem value
        self.assertIs(float, type(memory))
        self.assertGreaterEqual(memory, 0)
        self.assertLessEqual(memory, 100)
        # check handling of non-existing PID
        work, memory = instant_process_statistics(-1)
        self.assertEqual(work, 0)
        self.assertEqual(memory, 0)

    def test_cpu_process_statistics(self):
        """ Test the CPU of the process between 2 dates. """
        from supvisors.statistics import cpu_process_statistics
        stats = cpu_process_statistics(50, 20, 100)
        self.assertIs(float, type(stats))
        self.assertEqual(30, stats)

    def test_instant_statistics(self):
        """ Test the instant global statistics. """
        import multiprocessing, os, time
        from supvisors.statistics import instant_statistics
        stats = instant_statistics([('myself', os.getpid())])
        # check result
        self.assertEqual(5, len(stats))
        date, cpu_stats, mem_stats, io_stats, proc_stats = stats
        #  check time (current is greater)
        self.assertGreater(time.time(), date)
        # check cpu jiffies
        self.assertEqual(multiprocessing.cpu_count() + 1, len(cpu_stats))
        for cpu in cpu_stats:
            self.assertEqual(2, len(cpu))
            for value in cpu:
                self.assertIs(float, type(value))
        # check memory
        self.assertIs(float, type(mem_stats))
        self.assertGreaterEqual(mem_stats, 0)
        self.assertLessEqual(mem_stats, 100)
        # check io
        for intf, bytes in io_stats.items():
            self.assertIs(str, type(intf))
            self.assertEqual(2, len(bytes))
            for value in bytes:
                self.assertIs(int, type(value))
        # check process stats
        self.assertListEqual(['myself'], proc_stats.keys())
        values = proc_stats['myself']
        self.assertEqual(2, len(values))
        self.assertEqual(os.getpid(), values[0])
        self.assertEqual(2, len(values[1]))
        for value in values[1]:
            self.assertIs(float, type(value))
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)

    def test_statistics(self):
        """ Test the global statistics between 2 dates. """
        import multiprocessing, os, time
        from supvisors.statistics import instant_statistics, statistics
        named_pid = 'myself', os.getpid()
        ref_stats = instant_statistics([named_pid])
        time.sleep(2)
        last_stats = instant_statistics([named_pid])
        stats = statistics(last_stats, ref_stats)
        # check result
        self.assertEqual(5, len(stats))
        date, cpu_stats, mem_stats, io_stats, proc_stats = stats
        # check date
        self.assertEqual(last_stats[0], date)
        # check cpu
        self.assertEqual(multiprocessing.cpu_count() + 1, len(cpu_stats))
        for cpu in cpu_stats:
            self.assertIs(float, type(cpu))
            self.assertGreaterEqual(cpu, 0)
            self.assertLessEqual(cpu, 100)
        # check memory
        self.assertIs(float, type(mem_stats))
        self.assertEqual(last_stats[2], mem_stats)
        # check io
        for intf, bytes in io_stats.items():
            self.assertIs(str, type(intf))
            self.assertEqual(2, len(bytes))
            for value in bytes:
                self.assertIs(float, type(value))
        # check process stats
        self.assertListEqual([named_pid], proc_stats.keys())
        values = proc_stats[named_pid]
        self.assertEqual(2, len(values))
        for value in values:
            self.assertIs(float, type(value))
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)


class StatisticsInstanceTest(unittest.TestCase):
    """ Test case for the StatisticsInstance class of the statistics module. """

    def test_create(self):
        """ Test the initialization of an instance. """
        from supvisors.statistics import StatisticsInstance
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
        from supvisors.statistics import StatisticsInstance
        instance = StatisticsInstance(17, 10)
        # change values
        instance.counter = 28
        instance.ref_stats = ('dummy', 0)
        instance.cpu = [13.2,  14.8]
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
        from supvisors.statistics import StatisticsInstance
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
        from supvisors.statistics import StatisticsInstance
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
        from supvisors.statistics import StatisticsInstance
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
        self.assertListEqual([[6.25, 10.9375], [20.0, 19.5], [20.0, 16.0], [1.0, 0.0], [0.0, 15.0]], instance.cpu)
        self.assertListEqual([76.1, 75.9], instance.mem)
        self.assertDictEqual({'eth0': ([0.4, 0.8], [0.2, 0.2]), 'lo': ([0.1, 0.8], [0.1, 0.8])}, instance.io)
        self.assertEqual({('myself', 118612): ([0.5, 3.125], [1.9, 1.87]),
            ('other1', 8865): ([3.125], [1.87])}, instance.proc)
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
        self.assertListEqual([[ 10.9375, 5.0], [19.5, 10.0], [16.0, 0.0], [0.0, 1.5], [15.0, 1.25]], instance.cpu)
        self.assertListEqual([75.9, 74.7], instance.mem)
        self.assertDictEqual({'eth0': ([0.8, 0.4], [0.2, 0.8]), 'lo': ([0.8, 0.025], [0.8, 0.025])}, instance.io)
        self.assertEqual({('myself', 118612): ([3.125, 36.25], [1.87, 2.34]),
            ('other1', 8865): ([3.125, 36.25], [1.87, 2.34])}, instance.proc)
        self.assertIs(stats7, instance.ref_stats)


class StatisticsCompilerTest(unittest.TestCase):
    """ Test case for the StatisticsCompiler class of the statistics module. """

    def setUp(self):
        """ Create a dummy supvisors. """
        self.supvisors = DummySupvisors()

    def test_create(self):
        """ Test the initialization for statistics of all addresses. """
        from supvisors.statistics import StatisticsCompiler, StatisticsInstance
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
        from supvisors.statistics import StatisticsCompiler
        compiler = StatisticsCompiler(self.supvisors)
        # set data to a given address
        for address, period_instance in compiler.data.items():
            for period, instance in period_instance.items():
                instance.counter = 28
                instance.ref_stats = ('dummy', 0)
                instance.cpu = [13.2,  14.8]
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
                    self.assertListEqual([13.2,  14.8], instance.cpu)
                    self.assertListEqual([56.4, 71.3, 68.9], instance.mem)
                    self.assertDictEqual({'eth0': (123465, 654321), 'lo': (321, 321)}, instance.io)
                    self.assertDictEqual({('myself', 5888): (25.0, 12.5)}, instance.proc)

    def test_push_statistics(self):
        """ Test the storage of the instant statistics of an address. """
        from supvisors.statistics import StatisticsCompiler
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

