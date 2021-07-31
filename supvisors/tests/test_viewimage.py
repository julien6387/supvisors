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


from supvisors.viewimage import *

from .base import DummyHttpContext


def test_stats_image():
    """ Test the values set at construction. """
    image = StatsImage()
    assert image.contents is None
    # create a buffer
    contents = image.new_image()
    assert image.contents is not None
    assert image.contents is contents
    assert not contents.closed
    # create a buffer again
    image.new_image()
    assert contents is not None
    assert contents is not image.contents
    assert contents.closed
    assert not image.contents.closed


def test_address_instances():
    """ Test the values set at construction. """
    assert address_cpu_img is not None
    assert address_cpu_img.contents is None
    assert address_mem_img is not None
    assert address_mem_img.contents is None
    assert address_io_img is not None
    assert address_io_img.contents is None


def test_process_instances():
    """ Test the values set at construction. """
    assert process_cpu_img is not None
    assert process_cpu_img.contents is None
    assert process_mem_img is not None
    assert process_mem_img.contents is None


def test_image_view():
    """ Test the values set at construction. """
    # test creation
    image = StatsImage()
    view = ImageView(DummyHttpContext(), image)
    assert view.buffer is image
    # test render with an image having no contents
    response = view()
    headers = response['headers']
    assert headers['Content-Type'] == 'image/png'
    assert headers['Pragma'] == 'no-cache'
    assert headers['Cache-Control'] == 'no-cache'
    assert headers['Expires'] == 'Thu, 01 Jan 1970 00:00:00 GMT'
    assert b'' == response['body']
    # test render with an image having contents
    contents = image.new_image()
    contents.write(b'Dummy contents')
    response = view()
    headers = response['headers']
    assert headers['Content-Type'] == 'image/png'
    assert headers['Pragma'] == 'no-cache'
    assert headers['Cache-Control'] == 'no-cache'
    assert headers['Expires'] == 'Thu, 01 Jan 1970 00:00:00 GMT'
    assert response['body'] == b'Dummy contents'


def test_address_cpu_image_view():
    """ Test the values set at construction. """
    view = AddressCpuImageView(DummyHttpContext())
    assert view.buffer is address_cpu_img


def test_address_memory_image_view():
    """ Test the values set at construction. """
    view = AddressMemoryImageView(DummyHttpContext())
    assert view.buffer is address_mem_img


def test_address_network_image_view():
    """ Test the values set at construction. """
    view = AddressNetworkImageView(DummyHttpContext())
    assert view.buffer is address_io_img


def test_process_cpu_image_view():
    """ Test the values set at construction. """
    view = ProcessCpuImageView(DummyHttpContext())
    assert view.buffer is process_cpu_img


def test_process_memory_image_view():
    """ Test the values set at construction. """
    view = ProcessMemoryImageView(DummyHttpContext())
    assert view.buffer is process_mem_img
