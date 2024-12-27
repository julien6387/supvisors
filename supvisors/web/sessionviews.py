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
from enum import Enum
from typing import Dict, Optional, Tuple

from supervisor.loggers import Logger
from supervisor.medusa.http_server import get_header
from supervisor.web import VIEWS, ViewContext

from supvisors.ttypes import NameList
from .viewimage import TemporaryStatsImage, StatsView, SoftwareIconImage

# Cookie naming
HEADERS = 'headers'
SUPVISORS_SESSION = 'supvisors-session'
COOKIE = re.compile(f'Cookie: {SUPVISORS_SESSION}=(.*)', re.IGNORECASE)


def get_cookie(context: ViewContext):
    """ Get the cookie text from the Supervisor HTTP context. """
    return get_header(COOKIE, context.request.header)


# TODO: move elsewhere ?
class StatsType(Enum):
    """ The Supvisors statistics types. """
    HOST_CPU, HOST_MEM, HOST_NET_IO, HOST_DISK_IO, HOST_DISK_USAGE, PROCESS_CPU, PROCESS_MEM = range(7)


class SupvisorsSession:
    """ Class holding the statistics views for one user session. """

    # session cookie expiry duration
    EXPIRY_DURATION = 3600  # seconds

    def __init__(self, logger: Logger):
        """ Initialize the session attributes. """
        self.logger: Logger = logger
        # create a session id
        self.session_id: str = str(uuid.uuid4())
        # expiration date
        self.expiry_date = datetime.datetime.now() + datetime.timedelta(seconds=SupvisorsSession.EXPIRY_DURATION)
        # stats views belonging to the user session
        self.image_names: NameList[str] = []

    @property
    def expired(self) -> bool:
        return datetime.datetime.now() > self.expiry_date

    def get_image_name(self, stats_type: StatsType, identifier: str, period: float, specific: Optional[str] = None) -> str:
        """ Get a unique image name based on statistics data source. """
        elements = [stats_type.name.lower(), re.sub(r'\W+', '-', identifier), str(period), self.session_id]
        if specific:
            elements.insert(0, re.sub(r'\W+', '-', specific))
        return '{}.png'.format('_'.join(elements))

    def get_image(self, stats_type: StatsType, identifier: str, period: float,
                  specific: Optional[str] = None) -> Tuple[str, TemporaryStatsImage]:
        """ Get the image name and the associated buffer. """
        image_name = self.get_image_name(stats_type, identifier, period, specific)
        if image_name in VIEWS:
            stats_image = VIEWS[image_name]['buffer']
            stats_image.reset_expiry_date()
            return image_name, stats_image
        # create image if not existing
        stats_image = TemporaryStatsImage()
        # create entry in Supervisor views using the image name as a "template"
        VIEWS[image_name] = {'template': image_name, 'view': StatsView, 'buffer': stats_image}
        self.image_names.append(image_name)
        return image_name, stats_image

    def check_expiration(self):
        """ Delete the views that have expired in the session. """
        for image_name in list(self.image_names):
            # VIEWS entries with a buffer attribute are Supvisors stats views
            stats_image = VIEWS[image_name].get('buffer')
            if stats_image and stats_image.expired:
                self.logger.debug(f'SupvisorsSession.check_expiration: {image_name} has expired')
                del VIEWS[image_name]
                self.image_names.remove(image_name)

    def clear_views(self):
        """ Clear Supervisor VIEWS when the session has expired. """
        for image_name in self.image_names:
            del VIEWS[image_name]
        self.image_names = []


class SessionViews:
    """ Class handling the user web sessions. """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        self.active_sessions: Dict[str, SupvisorsSession] = {}
        # take into account icon option here
        SoftwareIconImage.set_path(supvisors.options.software_icon)

    @property
    def logger(self) -> Logger:
        """ Return the Supvisors logger. """
        return self.supvisors.logger

    def get_session(self, context: ViewContext) -> SupvisorsSession:
        """ Get or create the user session based on the Supervisor HTTP context. """
        # use the get_session call to check the sessions expiry date
        self.check_expiration()
        # look for the session based on the cookie eventually set
        cookie = get_cookie(context)
        self.logger.debug(f'SessionViews.get_session: found cookie={cookie}')
        if cookie and cookie in self.active_sessions:
            return self.active_sessions[cookie]
        # not found or expired
        session = SupvisorsSession(self.logger)
        self.active_sessions[session.session_id] = session
        # set the new cookie in the HTTP response with an expiry duration of 1 hour
        cookie = f'{SUPVISORS_SESSION}={session.session_id}'
        expiry_cookie = f'{cookie}; Max-Age={SupvisorsSession.EXPIRY_DURATION}'
        self.logger.debug(f'SessionViews.get_session: new cookie="{expiry_cookie}"')
        context.response[HEADERS]['Set-Cookie'] = expiry_cookie
        # force the cookie also in the HTTP request for further processing on the page requested ?
        context.request.header.insert(0, f'Cookie: {cookie}')
        return session

    def check_expiration(self):
        """ Delete the resources that have expired. """
        for session in list(self.active_sessions.values()):
            # check the session age
            if session.expired:
                self.logger.warn(f'SessionViews.check_expiration: {session.session_id} has expired')
                session.clear_views()
                del self.active_sessions[session.session_id]
            else:
                # clean up old images in the session
                session.check_expiration()
