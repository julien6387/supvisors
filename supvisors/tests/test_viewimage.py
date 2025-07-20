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

import supvisors
from supvisors.web.sessionviews import StatsType
from supvisors.web.viewimage import *


def test_stats_image():
    """ Test the StatsImage class. """
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


def test_temporary_stats_image():
    """ Test the TemporaryStatsImage class. """
    image = TemporaryStatsImage()
    assert isinstance(image, StatsImage)
    ref_date = image.expiry_date
    assert image.expiry_date > datetime.datetime.now()
    assert not image.expired
    image.expiry_date = datetime.datetime.now() - datetime.timedelta(seconds=1)
    assert image.expired
    # test date reset
    image.reset_expiry_date()
    assert image.expiry_date > ref_date
    assert not image.expired


def test_image_view(http_context):
    """ Test the ImageView class. """
    # test render with no image
    view = ImageView(http_context, None)
    assert view.context is http_context
    assert view.image is None
    response = view()
    headers = response['headers']
    assert headers['Content-Type'] == 'image/png'
    assert headers['Pragma'] == 'no-cache'
    assert headers['Cache-Control'] == 'no-cache'
    assert headers['Expires'] == 'Thu, 01 Jan 1970 00:00:00 GMT'
    assert b'' == response['body']
    # test render with an image having no contents
    image = StatsImage()
    view = ImageView(http_context, image)
    assert view.context is http_context
    assert view.image is image
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


def test_stats_view(supvisors_instance, http_context):
    """ Test the StatsView class. """
    # test with no corresponding image
    assert http_context.template.endswith('index.html')
    view = StatsView(http_context)
    assert view.context is http_context
    assert view.image is None
    # test with corresponding image
    session = supvisors_instance.sessions.get_session(http_context)
    image_name, image = session.get_image(StatsType.PROCESS_MEM, '10.0.0.1:25000', 5.0,
                                          specific='dummy_appli:dummy_process')
    http_context.template = image_name
    view = StatsView(http_context)
    assert view.image is image


def test_supervisor_icon_image():
    """ Test the SupervisorIconImage class. """
    # use no context to avoid image pre-fill
    SupervisorIconImage._icon = None
    # test default
    view = SupervisorIconImage(None)
    assert view.image is not None
    # test that a second instance would get the same object
    ref_buffer = view.image
    view = SupervisorIconImage(None)
    assert view.image is not None
    assert view.image is ref_buffer


def test_software_icon_image():
    """ Test the SoftwareIconImage class. """
    # use no context to avoid image pre-fill
    SoftwareIconImage._icon = None
    # test default
    view = SoftwareIconImage(None)
    assert view.image is None
    # load an image
    icon_path = os.path.join(os.path.dirname(supvisors.__file__), 'ui', 'img', 'icon.png')
    SoftwareIconImage.set_path(icon_path)
    view = SoftwareIconImage(None)
    assert view.image is not None
    # test that a second instance would get the same object
    ref_buffer = view.image
    view = SoftwareIconImage(None)
    assert view.image is not None
    assert view.image is ref_buffer
