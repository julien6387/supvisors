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

from io import BytesIO

from supervisor.compat import as_bytes
from supervisor.medusa.http_server import http_date


# exchange class for images
class StatsImage(object):
    """ Buffer class holding PNG contents. """

    def __init__(self):
        self.contents = None

    def new_image(self):
        if self.contents:
            self.contents.close()
        self.contents = BytesIO()
        return self.contents


# instance for image buffers
address_cpu_img = StatsImage()
address_mem_img = StatsImage()
address_io_img = StatsImage()

process_cpu_img = StatsImage()
process_mem_img = StatsImage()


# simple handlers for web images
class ImageView(object):
    content_type = 'image/png'
    delay = .5

    def __init__(self, context, buffer):
        self.context = context
        self.buffer = buffer

    def __call__(self):
        response = self.context.response
        headers = response['headers']
        headers['Content-Type'] = self.content_type
        headers['Pragma'] = 'no-cache'
        headers['Cache-Control'] = 'no-cache'
        headers['Expires'] = http_date.build_http_date(0)
        if self.buffer.contents:
            body = self.buffer.contents.getvalue()
        else:
            body = b""
        response['body'] = as_bytes(body)
        return response


class AddressCpuImageView(ImageView):
    """ Dummy view holding the Address CPU image. """

    def __init__(self, context):
        """ Link to the Address CPU buffer. """
        ImageView.__init__(self, context, address_cpu_img)


class AddressMemoryImageView(ImageView):
    """ Dummy view holding the Address Memory image. """

    def __init__(self, context):
        """ Link to the Address Memory buffer. """
        ImageView.__init__(self, context, address_mem_img)


class AddressNetworkImageView(ImageView):
    """ Dummy view holding the Address Network image. """

    def __init__(self, context):
        """ Link to the Address Network buffer. """
        ImageView.__init__(self, context, address_io_img)


class ProcessCpuImageView(ImageView):
    """ Dummy view holding the Process CPU image. """

    def __init__(self, context):
        """ Link to the Process CPU buffer. """
        ImageView.__init__(self, context, process_cpu_img)


class ProcessMemoryImageView(ImageView):
    """ Dummy view holding the Process Memory image. """

    def __init__(self, context):
        """ Link to the Process Memory buffer. """
        ImageView.__init__(self, context, process_mem_img)
