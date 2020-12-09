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
import os
import sys
import time
import unittest


class StatisticsCollectorTest(unittest.TestCase):
    """ Test case for the functions of the statscollector module. """

    def setUp(self):
        """ Skip the tests if psutil is not installed. """
        try:
            import psutil
            psutil.__name__
        except ImportError:
            raise unittest.SkipTest('cannot test as optional psutil is not installed')

    def test_instant_cpu_statistics(self):
        """ Test the instant CPU statistics. """
        from supvisors.statscollector import instant_cpu_statistics
        stats = list(instant_cpu_statistics())
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

    def test_instant_memory_statistics(self):
        """ Test the instant memory statistics. """
        from supvisors.statscollector import instant_memory_statistics
        stats = instant_memory_statistics()
        # test bounds (percent)
        self.assertIs(float, type(stats))
        self.assertGreaterEqual(stats, 0)
        self.assertLessEqual(stats, 100)

    def test_instant_io_statistics(self):
        """ Test the instant I/O statistics. """
        from supvisors.statscollector import instant_io_statistics
        stats = instant_io_statistics()
        # test interface names
        with open('/proc/net/dev') as netfile:
            # two first lines are title
            contents = netfile.readlines()[2:]
        interfaces = [intf.strip().split(':')[0] for intf in contents]
        self.assertListEqual(interfaces, list(stats.keys()))
        self.assertIn('lo', stats.keys())
        # test that values are pairs
        for intf, io_bytes in stats.items():
            self.assertEqual(2, len(io_bytes))
            for value in io_bytes:
                self.assertIs(int, type(value))
        # for loopback address, recv bytes equals sent bytes
        self.assertEqual(stats['lo'][0], stats['lo'][1])

    def test_instant_process_statistics(self):
        """ Test the instant process statistics. """
        from supvisors.statscollector import instant_process_statistics
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

    def test_instant_statistics(self):
        """ Test the instant global statistics. """
        from supvisors.statscollector import instant_statistics
        stats = instant_statistics([('myself', os.getpid())])
        # check result
        self.assertEqual(5, len(stats))
        date, cpu_stats, mem_stats, io_stats, proc_stats = stats
        #  check time (current is greater)
        self.assertGreater(time.time(), date)
        # check cpu jiffies
        self.assertEqual(multiprocessing.cpu_count() + 1, len(list(cpu_stats)))
        for cpu in cpu_stats:
            self.assertEqual(2, len(cpu))
            for value in cpu:
                self.assertIs(float, type(value))
        # check memory
        self.assertIs(float, type(mem_stats))
        self.assertGreaterEqual(mem_stats, 0)
        self.assertLessEqual(mem_stats, 100)
        # check io
        for intf, io_bytes in io_stats.items():
            self.assertIs(str, type(intf))
            self.assertEqual(2, len(io_bytes))
            for value in io_bytes:
                self.assertIs(int, type(value))
        # check process stats
        self.assertListEqual(['myself'], list(proc_stats.keys()))
        values = proc_stats['myself']
        self.assertEqual(2, len(values))
        self.assertEqual(os.getpid(), values[0])
        self.assertEqual(2, len(values[1]))
        for value in values[1]:
            self.assertIs(float, type(value))
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
