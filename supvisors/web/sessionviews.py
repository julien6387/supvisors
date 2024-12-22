# ======================================================================
# Copyright 2024 Julien LE CLEACH
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
import re
import uuid
from typing import Dict

from supervisor.medusa.http_server import get_header
from supervisor.web import VIEWS, ViewContext

from supvisors.web.viewimage import StatsImage, SoftwareIconImage, StatsViews

# Cookie naming
HEADERS = 'headers'
SUPVISORS_SESSION = 'supvisors-session'
COOKIE = re.compile(f'Cookie: {SUPVISORS_SESSION}=(.*)', re.IGNORECASE)


def get_cookie(context: ViewContext):
    """ TODO. """
    return get_header(COOKIE, context.request.header)


class SupvisorsSession:
    """ TODO. """

    def __init__(self):
        """ TODO. """
        # create a session id
        self.session_id: str = str(uuid.uuid4())
        # expiry date
        # self._expiry_date = datetime.datetime.now() + datetime.timedelta(hours=1)
        self._expiry_date = datetime.datetime.now() + datetime.timedelta(seconds=5)
        # host and process images
        self.images: Dict[StatsViews, StatsImage] = {view: StatsImage()
                                                     for view in StatsViews}
        # TODO
        self.add_views()

    @property
    def expiry_date(self) -> str:
        return self._expiry_date.strftime('%a, %d %b %Y %H:%M:%S GMT')

    @property
    def expired(self) -> bool:
        return datetime.datetime.now() > self._expiry_date

    def get_image_name(self, view: StatsViews) -> str:
        """ TODO. """
        return f'{view.name}_{self.session_id}.png'

    def get_image(self, view: StatsViews) -> StatsImage:
        """ TODO. """
        return self.images[view]

    def add_views(self):
        """ TODO. """
        for view in StatsViews:
            VIEWS[self.get_image_name(view)] = {'template': None, 'view': view.value}

    def clear_views(self):
        """ TODO. """
        for view in StatsViews:
            del VIEWS[self.get_image_name(view)]


class SessionViews:
    """ TODO. """

    def __init__(self, supvisors):
        """ TODO. """
        self.supvisors = supvisors
        self.active_sessions: Dict[str, SupvisorsSession] = {}
        # TODO: manage options at once
        SoftwareIconImage.set_path(supvisors.options.software_icon)

    @property
    def logger(self):
        return self.supvisors.logger

    def get_session(self, context: ViewContext):
        """ TODO. """
        # use the get_session call to check the sessions expiry date
        self.check_expiration()
        # look for the session based on the cookie eventually set
        cookie = get_cookie(context)
        self.logger.info(f'SessionViews.get_session: found cookie={cookie}')  # FIXME
        if cookie and cookie in self.active_sessions:
            return self.active_sessions[cookie]
        # not found or expired
        session = SupvisorsSession()
        self.active_sessions[session.session_id] = session
        # set the cookie in the HTTP response
        # cookie = f'{SUPVISORS_SESSION}={session.session_id}; expires={session.expiry_date}'  # TODO: try Max-Age=3600
        cookie = f'{SUPVISORS_SESSION}={session.session_id}; Max-Age=5'
        self.logger.info(f'SessionViews.get_session: new cookie="{cookie}"')  # FIXME
        context.response[HEADERS]['Set-Cookie'] = cookie
        # TODO: force the cookie also in the HTTP request for further processing on the page requested ?
        # context.request.header.insert(0, f'Cookie: {cookie}')
        return session

    def check_expiration(self):
        """ TODO. """
        for session in list(self.active_sessions.values()):
            if session.expired:
                self.logger.info(f'SessionViews.check_expiration: {session.session_id} has expired')  # FIXME
                session.clear_views()
                del self.active_sessions[session.session_id]
