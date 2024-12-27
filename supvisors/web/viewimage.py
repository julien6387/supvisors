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

import datetime
import io
import os
from typing import Optional

import supervisor
from supervisor.compat import as_bytes
from supervisor.medusa.http_server import http_date
from supervisor.web import VIEWS, ViewContext


# exchange class for images
class StatsImage:
    """ Buffer class holding image contents. """

    def __init__(self):
        """ Initialization of the attributes. """
        self.contents = None

    def new_image(self) -> io.BytesIO:
        """ Return a new BytesIO for the image. """
        if self.contents:
            self.contents.close()
        self.contents = io.BytesIO()
        return self.contents


class TemporaryStatsImage(StatsImage):
    """ StatsImage with an expiry date. """

    EXPIRY_DURATION = 5  # seconds

    def __init__(self):
        """ Initialization of the attributes. """
        super().__init__()
        self.expiry_date = None
        self.reset_expiry_date()

    @property
    def expired(self) -> bool:
        return datetime.datetime.now() > self.expiry_date

    def reset_expiry_date(self):
        """ When the image is being reused, reset the expiry date. """
        self.expiry_date = datetime.datetime.now() + datetime.timedelta(seconds=self.EXPIRY_DURATION)


class ImageView:
    """ Simple handler for web images. """

    # The delay constant is needed by Supervisor
    delay = .5

    def __init__(self, context: ViewContext, image: Optional[StatsImage]):
        """ Initialization of the attributes. """
        self.context: ViewContext = context
        self.image: Optional[StatsImage] = image

    def __call__(self):
        """ The ImageView instance is a callable. """
        response = self.context.response
        headers = response['headers']
        headers['Content-Type'] = 'image/png'
        headers['Pragma'] = 'no-cache'
        headers['Cache-Control'] = 'no-cache'
        headers['Expires'] = http_date.build_http_date(0)
        if self.image and self.image.contents:
            body = self.image.contents.getvalue()
        else:
            body = b''
        response['body'] = as_bytes(body)
        return response


class StatsView(ImageView):
    """ View dedicated to the display of a statistics diagram. """

    def __init__(self, context: ViewContext):
        """ Use context template to get image identification. """
        # get the image buffer from the image name set in the template attribute
        stats_image = VIEWS.get(context.template, {}).get('buffer')
        # call the Image View constructor with the image buffer
        ImageView.__init__(self, context, stats_image)



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

    _icon: Optional[StatsImage] = None

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

    _icon: Optional[StatsImage] = None

    def __init__(self, context):
        """ Link to the Process Memory buffer. """
        ImageView.__init__(self, context, self._icon)

    @staticmethod
    def set_path(icon_path: str) -> None:
        """ Load the user software icon into a BytesIO. """
        if not SoftwareIconImage._icon and icon_path:
            SoftwareIconImage._icon = create_icon(icon_path)
