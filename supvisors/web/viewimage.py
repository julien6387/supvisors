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
from enum import Enum

import supervisor
from supervisor.compat import as_bytes
from supervisor.medusa.http_server import http_date
from supervisor.web import ViewContext


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


# simple handlers for web images
class ImageView:
    """ TODO. """

    content_type = 'image/png'
    delay = .5

    def __init__(self, context: ViewContext, image: StatsImage):
        self.context: ViewContext = context
        self.buffer = image

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


def get_session(context: ViewContext):
    """ TODO. """
    return context.supervisord.supvisors.sessions.get_session(context)


class HostCpuImageView(ImageView):
    """ Dummy view holding the Host CPU image. """

    def __init__(self, context: ViewContext):
        """ Link to the Host CPU buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.host_cpu))


class HostMemoryImageView(ImageView):
    """ Dummy view holding the Host Memory image. """

    def __init__(self, context: ViewContext):
        """ Link to the Host Memory buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.host_mem))


class HostNetworkIoImageView(ImageView):
    """ Dummy view holding the Host Network IO image. """

    def __init__(self, context: ViewContext):
        """ Link to the Host Network IO buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.host_net_io))


class HostDiskIoImageView(ImageView):
    """ Dummy view holding the Host Disk IO image. """

    def __init__(self, context: ViewContext):
        """ Link to the Host Network buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.host_disk_io))


class HostDiskUsageImageView(ImageView):
    """ Dummy view holding the Host Disk usage image. """

    def __init__(self, context: ViewContext):
        """ Link to the Host Disk usage buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.host_disk_usage))


class ProcessCpuImageView(ImageView):
    """ Dummy view holding the Process CPU image. """

    def __init__(self, context: ViewContext):
        """ Link to the Process CPU buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.process_cpu))


class ProcessMemoryImageView(ImageView):
    """ Dummy view holding the Process Memory image. """

    def __init__(self, context: ViewContext):
        """ Link to the Process Memory buffer. """
        ImageView.__init__(self, context, get_session(context).get_image(StatsViews.process_mem))


class StatsViews(Enum):
    """ TODO. """
    host_cpu = HostCpuImageView
    host_mem = HostMemoryImageView
    host_net_io = HostNetworkIoImageView
    host_disk_io = HostDiskIoImageView
    host_disk_usage = HostDiskUsageImageView
    process_cpu = ProcessCpuImageView
    process_mem = ProcessMemoryImageView


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
