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

import io
import os

import supervisor
from supervisor.compat import as_bytes
from supervisor.medusa.http_server import http_date


# exchange class for images
class StatsImage:
    """ Buffer class holding PNG contents. """

    def __init__(self):
        self.contents = None

    def new_image(self):
        if self.contents:
            self.contents.close()
        self.contents = io.BytesIO()
        return self.contents


# instance for image buffers
host_cpu_img = StatsImage()
host_mem_img = StatsImage()
host_net_io_img = StatsImage()
host_disk_io_img = StatsImage()
host_disk_usage_img = StatsImage()

process_cpu_img = StatsImage()
process_mem_img = StatsImage()


# simple handlers for web images
class ImageView:
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


class HostCpuImageView(ImageView):
    """ Dummy view holding the Host CPU image. """

    def __init__(self, context):
        """ Link to the Host CPU buffer. """
        ImageView.__init__(self, context, host_cpu_img)


class HostMemoryImageView(ImageView):
    """ Dummy view holding the Host Memory image. """

    def __init__(self, context):
        """ Link to the Host Memory buffer. """
        ImageView.__init__(self, context, host_mem_img)


class HostNetworkIoImageView(ImageView):
    """ Dummy view holding the Host Network IO image. """

    def __init__(self, context):
        """ Link to the Host Network IO buffer. """
        ImageView.__init__(self, context, host_net_io_img)


class HostDiskIoImageView(ImageView):
    """ Dummy view holding the Host Disk IO image. """

    def __init__(self, context):
        """ Link to the Host Network buffer. """
        ImageView.__init__(self, context, host_disk_io_img)


class HostDiskUsageImageView(ImageView):
    """ Dummy view holding the Host Disk usage image. """

    def __init__(self, context):
        """ Link to the Host Disk usage buffer. """
        ImageView.__init__(self, context, host_disk_usage_img)


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


# Trick to make available the Supervisor icon from Supvisors Web UI
# There might be a better way in medusa but TBD
def create_icon(icon_path) -> StatsImage:
    """ Load an image into a BytesIO. """
    icon = StatsImage()
    with io.open(icon_path, 'rb') as fic:
        icon.contents = io.BytesIO(fic.read())
    return icon


class SupervisorIconImage(ImageView):
    """ Dummy view holding the Supervisor Icon. """

    _icon: StatsImage = None

    def __init__(self, context):
        """ Link to the Process Memory buffer. """
        ImageView.__init__(self, context, self.icon)

    @property
    def icon(self) -> StatsImage:
        """ Load the Supervisor icon into a BytesIO. """
        if not SupervisorIconImage._icon:
            icon_path = os.path.join(os.path.dirname(supervisor.__file__), 'ui', 'images', 'icon.png')
            SupervisorIconImage._icon = create_icon(icon_path)
        return SupervisorIconImage._icon


class SoftwareIconImage(ImageView):
    """ Dummy view holding the Process Memory image. """

    _icon: StatsImage = None

    def __init__(self, context):
        """ Link to the Process Memory buffer. """
        ImageView.__init__(self, context, self._icon)

    @staticmethod
    def set_path(icon_path: str) -> None:
        """ Load the user software icon into a BytesIO. """
        if not SoftwareIconImage._icon and icon_path:
            SoftwareIconImage._icon = create_icon(icon_path)
