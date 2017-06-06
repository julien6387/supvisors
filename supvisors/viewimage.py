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

from io import BytesIO

from supervisor.web import MeldView


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
address_cpu_image = StatsImage()
address_mem_image = StatsImage()
address_io_image = StatsImage()

process_cpu_image = StatsImage()
process_mem_image = StatsImage()


# simple handlers for web images
class ImageView(MeldView):
    """ Dummy view holding an image. """

    def __init__(self, context, buffer):
        """ Storage of the reference to the buffer. """
        MeldView.__init__(self, context)
        self.buffer = buffer

    def render(self):
        """ Export the internal memory buffer. """
        if self.buffer.contents:
            return self.buffer.contents.getvalue()
        return self.clone().write_xhtmlstring()


class AddressCpuImageView(ImageView):
    """ Dummy view holding the Address CPU image. """

    def __init__(self, context):
        """ Link to the Address CPU buffer. """
        ImageView.__init__(self, context, address_cpu_image)


class AddressMemoryImageView(ImageView):
    """ Dummy view holding the Address Memory image. """

    def __init__(self, context):
        """ Link to the Address Memory buffer. """
        ImageView.__init__(self, context, address_mem_image)


class AddressNetworkImageView(ImageView):
    """ Dummy view holding the Address Network image. """

    def __init__(self, context):
        """ Link to the Address Network buffer. """
        ImageView.__init__(self, context, address_io_image)


class ProcessCpuImageView(ImageView):
    """ Dummy view holding the Process CPU image. """

    def __init__(self, context):
        """ Link to the Process CPU buffer. """
        ImageView.__init__(self, context, process_cpu_image)


class ProcessMemoryImageView(ImageView):
    """ Dummy view holding the Process Memory image. """

    def __init__(self, context):
        """ Link to the Process Memory buffer. """
        ImageView.__init__(self, context, process_mem_image)

