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

from supvisors.tests.base import DummyClass, DummyHttpContext


class ViewImageTest(unittest.TestCase):
    """ Test case for the viewimage module. """

    def test_address_stats_images(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import address_cpu_image, address_mem_image, address_io_image
        self.assertIsNotNone(address_cpu_image)
        self.assertIsNotNone(address_mem_image)
        self.assertIsNotNone(address_io_image)

    def test_process_stats_images(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import process_cpu_image, process_mem_image
        self.assertIsNotNone(process_cpu_image)
        self.assertIsNotNone(process_mem_image)

    def test_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ImageView
        view = ImageView(DummyHttpContext('ui/empty.html'),  DummyClass())
        self.assertIsNotNone(view)

    def test_address_cpu_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressCpuImageView
        view = AddressCpuImageView(DummyHttpContext('ui/empty.html'))
        self.assertIsNotNone(view)

    def test_address_memory_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressMemoryImageView
        view = AddressMemoryImageView(DummyHttpContext('ui/empty.html'))
        self.assertIsNotNone(view)

    def test_address_network_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressNetworkImageView
        view = AddressNetworkImageView(DummyHttpContext('ui/empty.html'))
        self.assertIsNotNone(view)

    def test_process_cpu_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ProcessCpuImageView
        view = ProcessCpuImageView(DummyHttpContext('ui/empty.html'))
        self.assertIsNotNone(view)

    def test_process_memory_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ProcessMemoryImageView
        view = ProcessMemoryImageView(DummyHttpContext('ui/empty.html'))
        self.assertIsNotNone(view)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
