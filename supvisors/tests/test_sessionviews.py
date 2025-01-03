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

import os
from datetime import timezone

import supvisors
from supvisors.web.sessionviews import *
from supvisors.web.viewimage import StatsImage


def test_get_cookie(http_context):
    """ Test the get_cookie function. """
    # test when no cookie set
    assert get_cookie(http_context) == ''
    # set cookie and test
    http_context.request.header.append('Cookie: supvisors-session=1234')
    assert get_cookie(http_context) == '1234'


def test_supvisors_session(mocker, logger_instance):
    """ Test the SupvisorsSession class. """
    mocker.patch('uuid.uuid4', return_value=1234)
    mocker.patch('datetime.datetime', **{'now.return_value': datetime.datetime(2024, 12, 22, 15, 25, 38, 409000,
                                                                               tzinfo=timezone.utc)})
    # test the construction
    session = SupvisorsSession(logger_instance)
    assert session.session_id == '1234'
    assert session.expiry_date.timestamp() == 1734884738.409
    assert session.image_names == []
    assert not session.expired
    # initial status
    nb_views = len(VIEWS)
    # test get non-existing image / no specific
    image_name_1, image_1 = session.get_image(StatsType.HOST_CPU, '10.0.0.1:25000', 5.2)
    assert image_name_1 == 'host_cpu_10-0-0-1-25000_5.2_1234.png'
    assert isinstance(image_1, TemporaryStatsImage)
    assert len(VIEWS) == nb_views + 1
    assert image_name_1 in VIEWS
    assert VIEWS[image_name_1]['template'] == image_name_1
    assert VIEWS[image_name_1]['buffer'] is image_1
    assert session.image_names == [image_name_1]
    # test get existing image / no specific
    image_name_1, image_1bis = session.get_image(StatsType.HOST_CPU, '10.0.0.1:25000', 5.2)
    assert image_name_1 == 'host_cpu_10-0-0-1-25000_5.2_1234.png'
    assert image_1bis is image_1
    assert len(VIEWS) == nb_views + 1
    assert session.image_names == [image_name_1]
    # test get non-existing image / specific
    image_name_2, image_2 = session.get_image(StatsType.PROCESS_MEM, '10.0.0.2:25000', 10.1,
                                              specific='dummy_appli:dummy_process')
    assert image_name_2 == 'dummy_appli-dummy_process_process_mem_10-0-0-2-25000_10.1_1234.png'
    assert isinstance(image_2, TemporaryStatsImage)
    assert image_2.expiry_date.timestamp() == 1734881143.409
    assert len(VIEWS) == nb_views + 2
    assert image_name_2 in VIEWS
    assert VIEWS[image_name_2]['template'] == image_name_2
    assert VIEWS[image_name_2]['buffer'] is image_2
    assert session.image_names == [image_name_1, image_name_2]
    # test get existing image / specific (with date reset)
    image_2.expiry_date = datetime.datetime.now() - datetime.timedelta(seconds=1)
    assert image_2.expiry_date.timestamp() == 1734881137.409
    image_name_2, image_2bis = session.get_image(StatsType.PROCESS_MEM, '10.0.0.2:25000', 10.1,
                                                 specific='dummy_appli:dummy_process')
    assert image_name_2 == 'dummy_appli-dummy_process_process_mem_10-0-0-2-25000_10.1_1234.png'
    assert image_2bis is image_2
    assert image_2.expiry_date.timestamp() == 1734881143.409
    assert len(VIEWS) == nb_views + 2
    assert session.image_names == [image_name_1, image_name_2]
    # test no expiration
    session.check_expiration()
    assert image_name_1 in VIEWS
    assert image_name_2 in VIEWS
    assert session.image_names == [image_name_1, image_name_2]
    # test expiration on first view
    image_1.expiry_date = datetime.datetime.now() - datetime.timedelta(seconds=1)
    session.check_expiration()
    assert len(VIEWS) == nb_views + 1
    assert image_name_1 not in VIEWS
    assert image_name_2 in VIEWS
    assert session.image_names == [image_name_2]
    # test get formerly existing image / no specific
    image_name_1, image_1ter = session.get_image(StatsType.HOST_CPU, '10.0.0.1:25000', 5.2)
    assert image_name_1 == 'host_cpu_10-0-0-1-25000_5.2_1234.png'
    assert image_1ter is not image_1
    assert len(VIEWS) == nb_views + 2
    assert session.image_names == [image_name_2, image_name_1]
    # test expiration on session
    session.expiry_date = datetime.datetime.now() - datetime.timedelta(seconds=1)
    assert session.expired
    # test clear_views
    session.clear_views()
    assert len(VIEWS) == nb_views
    assert image_name_1 not in VIEWS
    assert image_name_2 not in VIEWS
    assert session.image_names == []


def test_session_views(mocker, supvisors_instance, http_context):
    """ Test the SessionViews class. """
    mocker.patch('uuid.uuid4', side_effect=['1234', '12345'])
    # test initial status
    assert SoftwareIconImage._icon is None
    # test creation with no user software icon
    sessions = SessionViews(supvisors_instance)
    assert sessions.supvisors is supvisors_instance
    assert sessions.logger is supvisors_instance.logger
    assert sessions.active_sessions == {}
    assert SoftwareIconImage._icon is None
    # test creation with user software icon
    icon_path = os.path.join(os.path.dirname(supvisors.__file__), 'ui', 'img', 'icon.png')
    supvisors_instance.options.software_icon = icon_path
    sessions = SessionViews(supvisors_instance)
    assert isinstance(SoftwareIconImage._icon, StatsImage)
    # add new session when no cookie set
    session_1 = sessions.get_session(http_context)
    assert sessions.active_sessions == {'1234': session_1}
    assert http_context.response[HEADERS]['Set-Cookie'] == 'supvisors-session=1234; Max-Age=3600'
    assert 'Cookie: supvisors-session=1234' in http_context.request.header
    # get session when cookie set
    session_1bis = sessions.get_session(http_context)
    assert session_1bis is session_1
    assert sessions.active_sessions == {'1234': session_1}
    # add new session when cookie unknown
    http_context.request.header.remove('Cookie: supvisors-session=1234')
    http_context.request.header.insert(0, 'Cookie: supvisors-session=4321')
    session_2 = sessions.get_session(http_context)
    assert sessions.active_sessions == {'1234': session_1, '12345': session_2}
    assert http_context.response[HEADERS]['Set-Cookie'] == 'supvisors-session=12345; Max-Age=3600'
    assert 'Cookie: supvisors-session=12345' in http_context.request.header
    # test no change in check_expiration
    image_name_1, image_1 = session_1.get_image(StatsType.HOST_NET_IO, '10.0.0.1:25000', 2.5, specific='eth0')
    image_name_2, image_2 = session_2.get_image(StatsType.HOST_DISK_USAGE, '10.0.0.1:25000', 2.5, specific='/usr/lib')
    assert not session_1.expired
    assert not session_2.expired
    assert not image_1.expired
    assert not image_2.expired
    sessions.check_expiration()
    assert sessions.active_sessions == {'1234': session_1, '12345': session_2}
    assert session_1.image_names == [image_name_1]
    assert session_2.image_names == [image_name_2]
    assert image_name_1 in VIEWS
    assert image_name_2 in VIEWS
    # test session image expiration
    image_1.expiry_date = datetime.datetime.now() - datetime.timedelta(seconds=1)
    sessions.check_expiration()
    assert sessions.active_sessions == {'1234': session_1, '12345': session_2}
    assert session_1.image_names == []
    assert session_2.image_names == [image_name_2]
    assert image_name_1 not in VIEWS
    assert image_name_2 in VIEWS
    # test session expiration
    session_2.expiry_date = datetime.datetime.now() - datetime.timedelta(seconds=1)
    sessions.check_expiration()
    assert sessions.active_sessions == {'1234': session_1}
    assert session_1.image_names == []
    assert image_name_1 not in VIEWS
    assert image_name_2 not in VIEWS
