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

import sys
import unittest

from supvisors.tests.base import DummyHttpContext


class StatsImageTest(unittest.TestCase):
    """ Test case for the StatsImage class of the viewimage module. """

    def test_stats_image(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import StatsImage
        image = StatsImage()
        self.assertIsNone(image.contents)
        # create a buffer
        contents = image.new_image()
        self.assertIsNotNone(image.contents)
        self.assertIs(contents, image.contents)
        self.assertFalse(contents.closed)
        # create a buffer again
        image.new_image()
        self.assertIsNotNone(image.contents)
        self.assertIsNot(contents, image.contents)
        self.assertTrue(contents.closed)
        self.assertFalse(image.contents.closed)

    def test_address_instances(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import (address_cpu_img,
                                         address_mem_img,
                                         address_io_img)
        self.assertIsNotNone(address_cpu_img)
        self.assertIsNone(address_cpu_img.contents)
        self.assertIsNotNone(address_mem_img)
        self.assertIsNone(address_mem_img.contents)
        self.assertIsNotNone(address_io_img)
        self.assertIsNone(address_io_img.contents)

    def test_process_instances(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import process_cpu_img, process_mem_img
        self.assertIsNotNone(process_cpu_img)
        self.assertIsNone(process_cpu_img.contents)
        self.assertIsNotNone(process_mem_img)
        self.assertIsNone(process_mem_img.contents)


class ImageViewTest(unittest.TestCase):
    """ Test case for the ImageView class of the viewimage module. """

    def test_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ImageView, StatsImage
        # test creation
        image = StatsImage()
        view = ImageView(DummyHttpContext(), image)
        self.assertIs(image, view.buffer)
        # test render with an image having no contents
        response = view()
        headers = response['headers']
        self.assertEqual('image/png', headers['Content-Type'])
        self.assertEqual('no-cache', headers['Pragma'])
        self.assertEqual('no-cache', headers['Cache-Control'])
        self.assertEqual('Thu, 01 Jan 1970 00:00:00 GMT', headers['Expires'])
        self.assertEqual(response['body'], b'')
        # test render with an image having contents
        contents = image.new_image()
        contents.write(b'Dummy contents')
        response = view()
        headers = response['headers']
        self.assertEqual('image/png', headers['Content-Type'])
        self.assertEqual('no-cache', headers['Pragma'])
        self.assertEqual('no-cache', headers['Cache-Control'])
        self.assertEqual('Thu, 01 Jan 1970 00:00:00 GMT', headers['Expires'])
        self.assertEqual(b'Dummy contents', response['body'])

    def test_address_cpu_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressCpuImageView, address_cpu_img
        view = AddressCpuImageView(DummyHttpContext())
        self.assertIs(view.buffer, address_cpu_img)

    def test_address_memory_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressMemoryImageView, address_mem_img
        view = AddressMemoryImageView(DummyHttpContext())
        self.assertIs(view.buffer, address_mem_img)

    def test_address_network_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import AddressNetworkImageView, address_io_img
        view = AddressNetworkImageView(DummyHttpContext())
        self.assertIs(view.buffer, address_io_img)

    def test_process_cpu_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ProcessCpuImageView, process_cpu_img
        view = ProcessCpuImageView(DummyHttpContext())
        self.assertIs(view.buffer, process_cpu_img)

    def test_process_memory_image_view(self):
        """ Test the values set at construction. """
        from supvisors.viewimage import ProcessMemoryImageView, process_mem_img
        view = ProcessMemoryImageView(DummyHttpContext())
        self.assertIs(view.buffer, process_mem_img)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
