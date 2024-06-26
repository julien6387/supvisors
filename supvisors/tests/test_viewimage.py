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


from supvisors.web.viewimage import *

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


def test_host_instances():
    """ Test the values set at construction. """
    assert host_cpu_img is not None
    assert host_cpu_img.contents is None
    assert host_mem_img is not None
    assert host_mem_img.contents is None
    assert host_net_io_img is not None
    assert host_net_io_img.contents is None
    assert host_disk_io_img is not None
    assert host_disk_io_img.contents is None
    assert host_disk_usage_img is not None
    assert host_disk_usage_img.contents is None


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


def test_host_cpu_image_view():
    """ Test the HostCpuImageView class. """
    view = HostCpuImageView(DummyHttpContext())
    assert view.buffer is host_cpu_img


def test_host_memory_image_view():
    """ Test the HostMemoryImageView class. """
    view = HostMemoryImageView(DummyHttpContext())
    assert view.buffer is host_mem_img


def test_host_network_io_image_view():
    """ Test the HostNetworkIoImageView class. """
    view = HostNetworkIoImageView(DummyHttpContext())
    assert view.buffer is host_net_io_img


def test_host_disk_io_image_view():
    """ Test the HostDiskIoImageView class. """
    view = HostDiskIoImageView(DummyHttpContext())
    assert view.buffer is host_disk_io_img


def test_host_disk_usage_image_view():
    """ Test the HostDiskUsageImageView class. """
    view = HostDiskUsageImageView(DummyHttpContext())
    assert view.buffer is host_disk_usage_img


def test_process_cpu_image_view():
    """ Test the ProcessCpuImageView class. """
    view = ProcessCpuImageView(DummyHttpContext())
    assert view.buffer is process_cpu_img


def test_process_memory_image_view():
    """ Test the ProcessMemoryImageView class. """
    view = ProcessMemoryImageView(DummyHttpContext())
    assert view.buffer is process_mem_img


def test_supervisor_icon_image():
    """ Test the SupervisorIconImage class. """
    # test default
    view = SupervisorIconImage(DummyHttpContext())
    assert view.buffer is not None
    # test that a second instance would get the same object
    ref_buffer = view.buffer
    view = SupervisorIconImage(DummyHttpContext())
    assert view.buffer is not None
    assert view.buffer is ref_buffer


def test_software_icon_image():
    """ Test the SoftwareIconImage class. """
    # test default
    view = SoftwareIconImage(DummyHttpContext())
    assert view.buffer is None
    # load an image
    icon_path = os.path.join(os.path.dirname(supervisor.__file__), 'ui', 'images', 'icon.png')
    SoftwareIconImage.set_path(icon_path)
    view = SoftwareIconImage(DummyHttpContext())
    assert view.buffer is not None
    # test that a second instance would get the same object
    ref_buffer = view.buffer
    view = SoftwareIconImage(DummyHttpContext())
    assert view.buffer is not None
    assert view.buffer is ref_buffer
