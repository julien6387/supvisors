# ======================================================================
# Copyright 2018 Julien LE CLEACH
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

import socket
import time
from unittest.mock import call, Mock

import pytest
from supervisor.http import NOT_DONE_YET
from supervisor.states import SupervisorStates, ProcessStates

from supvisors import __version__
from supvisors.ttypes import ApplicationStates, StartingStrategies, SupvisorsStates, SupvisorsInstanceStates
from supvisors.web.viewcontext import PROCESS, ViewContext
from supvisors.web.viewhandler import ViewHandler
from supvisors.web.viewimage import process_cpu_img, process_mem_img
from supvisors.web.webutils import MASTER_SYMBOL, SHEX_SHRINK, SHEX_EXPAND
from .base import DummyHttpContext
from .conftest import create_element, create_application


@pytest.fixture
def http_context(supvisors):
    """ Fixture for a consistent mocked HTTP context provided by Supervisor. """
    http_context = DummyHttpContext('ui/index.html')
    http_context.supervisord.supvisors = supvisors
    supvisors.supervisor_data.supervisord = http_context.supervisord
    return http_context


@pytest.fixture
def handler(http_context):
    """ Fixture for the instance to test. """
    return ViewHandler(http_context)


def test_init(http_context, handler):
    """ Test the values set at construction. """
    assert handler.root is not None
    assert handler.root.findmeld('version_mid') is not None
    assert handler.callback is None
    # test MeldView inheritance
    assert handler.context == http_context
    # test ViewHandler initialization
    assert handler.page_name is None
    current_time = time.time()
    current_mtime = time.monotonic()
    assert current_time - 1 < handler.current_time < current_time
    assert current_mtime - 1 < handler.current_mtime < current_mtime
    assert handler.supvisors is http_context.supervisord.supvisors
    assert handler.sup_ctx is http_context.supervisord.supvisors.context
    assert handler.local_identifier == handler.supvisors.mapper.local_identifier
    assert handler.has_host_statistics
    assert handler.has_process_statistics
    assert handler.view_ctx is None


def test_call(mocker, handler):
    """ Test the call method. """
    mocker.patch('supvisors.web.viewhandler.MeldView.__call__', side_effect=(NOT_DONE_YET, {'body': u'html_body'}))
    # first call to MeldView returns NOT_DONE_YET
    assert handler.__call__() is NOT_DONE_YET
    # second call to MeldView returns an HTML struct
    assert handler.__call__() == {'body': b'html_body'}


def test_render_action_in_progress(mocker, handler):
    """ Test the render method when Supervisor is in RUNNING state and when an action is in progress. """
    mocked_style = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_style')
    mocked_common = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_common')
    mocked_nav = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_navigation')
    mocked_header = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_header')
    mocked_contents = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_contents')
    mocked_clone = mocker.patch('supervisor.web.MeldView.clone')
    mocked_action = mocker.patch('supvisors.web.viewhandler.ViewHandler.handle_action')
    # build xml template
    header_elt = create_element()
    contents_elt = create_element()
    mocked_root = create_element({'header_mid': header_elt, 'contents_mid': contents_elt})
    mocked_root.write_xhtmlstring.return_value = 'xhtml'
    mocked_clone.return_value = mocked_root
    # patch context
    handler.supvisors.context.get_all_namespecs = Mock(return_value=[])
    # 1. test render call when an action is in progress
    handler.context.supervisord.options.mood = SupervisorStates.RUNNING
    mocked_action.return_value = NOT_DONE_YET
    assert handler.render() is NOT_DONE_YET
    assert handler.view_ctx is not None
    assert mocked_action.call_args_list == [call()]
    assert not mocked_clone.call_count
    assert not mocked_style.called
    assert not mocked_common.called
    assert not mocked_nav.called
    assert not mocked_header.call_count
    assert not mocked_contents.call_count
    # 2. test render call when no action is in progress
    mocked_action.reset_mock()
    mocked_action.return_value = None
    assert handler.render() == 'xhtml'
    assert handler.view_ctx is not None
    assert mocked_action.call_args_list == [call()]
    assert mocked_clone.call_args_list == [call()]
    assert mocked_style.call_args_list == [call(mocked_root)]
    assert mocked_common.call_args_list == [call(mocked_root)]
    assert mocked_header.call_args_list == [call(header_elt)]
    assert mocked_nav.call_args_list == [call(mocked_root)]
    assert mocked_contents.call_args_list == [call(contents_elt)]


def test_handle_parameters(supvisors, handler):
    """ Test the handle_parameters method. """
    supvisors.context.get_all_namespecs = Mock(return_value=[])
    assert handler.view_ctx is None
    handler.handle_parameters()
    assert handler.view_ctx is not None
    assert isinstance(handler.view_ctx, ViewContext)


def test_write_common(mocker, supvisors, handler):
    """ Test the write_common method. """
    mocked_msg = mocker.patch('supvisors.web.viewhandler.print_message')
    # patch context
    handler.page_name = 'dummy.html'
    handler.view_ctx = Mock(auto_refresh=True, gravity='severe', message='a message',
                            **{'format_url.return_value': 'an url'})
    # build xml template
    footer_mid = create_element()
    mocked_meta = create_element()
    mocked_supv = create_element()
    mocked_version = create_element()
    mocked_root = create_element({'meta_mid': mocked_meta, 'supvisors_mid': mocked_supv,
                                  'version_mid': mocked_version, 'footer_mid': footer_mid})
    # 1. test no conflict and auto-refresh
    supvisors.fsm.state = SupvisorsStates.OPERATION
    handler.write_common(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('version_mid'), call('footer_mid')]
    assert not mocked_meta.deparent.called
    assert 'failure' not in mocked_supv.attrib['class']
    assert mocked_version.content.call_args_list == [call(__version__)]
    assert mocked_msg.call_args_list == [call(footer_mid, 'severe', 'a message',
                                              handler.current_time, handler.local_nick_identifier)]
    # reset mocks
    mocked_root.reset_all()
    mocked_msg.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    # 2. test conflicts and no auto-refresh
    supvisors.fsm.state = SupvisorsStates.CONCILIATION
    mocker.patch.object(handler.sup_ctx, 'conflicts', return_value=True)
    handler.view_ctx.auto_refresh = False
    handler.write_common(mocked_root)
    assert mocked_root.findmeld.call_args_list == [call('meta_mid'), call('supvisors_mid'), call('version_mid'),
                                                   call('footer_mid')]
    assert mocked_meta.deparent.called
    assert mocked_supv.attrib == {'class': 'failure'}
    assert mocked_version.content.call_args_list == [call(__version__)]
    assert mocked_msg.call_args_list == [call(footer_mid, 'severe', 'a message',
                                              handler.current_time, handler.local_nick_identifier)]


def test_write_navigation(handler):
    """ Test the write_navigation method. """
    with pytest.raises(NotImplementedError):
        handler.write_navigation(Mock())


def test_write_nav(mocker, handler):
    """ Test the write_nav method. """
    mocked_appli = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_nav_applications')
    mocked_instances = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_nav_instances')
    handler.write_nav('root', 'identifier', 'appli')
    assert mocked_instances.call_args_list == [call('root', 'identifier')]
    assert mocked_appli.call_args_list == [call('root', 'appli')]


def test_write_nav_instances_identifier_error(supvisors, handler):
    """ Test the write_nav_instances method with an identifier not existing in supvisors context.
    Use discovery mode to test Supvisors instances ordering in this case. """
    supvisors.options.multicast_group = '293.0.0.1:7777'
    # patch the meld elements
    href_elt = Mock(attrib={})
    address_elt = Mock(attrib={}, **{'findmeld.return_value': href_elt})
    mocked_mid = Mock(**{'repeat.return_value': [(address_elt, '10.0.0.0')]})
    mocked_root = Mock(**{'findmeld.return_value': mocked_mid})
    # test call with no address status in context
    handler.write_nav_instances(mocked_root, '10.0.0.0')
    assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
    fqdn = socket.getfqdn()
    expected = ['10.0.0.1:25000', '10.0.0.2:25000', '10.0.0.3:25000', '10.0.0.4:25000', '10.0.0.5:25000',
                f'{fqdn}:25000', f'{fqdn}:15000']
    assert mocked_mid.repeat.call_args_list == [call(expected)]
    assert address_elt.findmeld.call_args_list == []


def test_write_nav_instances_silent_instance(supvisors, handler):
    """ Test the write_nav_instances method using a SILENT address. """
    # patch the meld elements
    instance_sp_mid = create_element()
    master_sp_mid = create_element()
    instance_a_mid = create_element({'instance_sp_mid': instance_sp_mid, 'master_sp_mid': master_sp_mid})
    instance_h_mid = create_element()
    instance_elt = create_element({'instance_a_mid': instance_a_mid})
    instance_li_mid = create_element()
    instance_li_mid.repeat.return_value = [(instance_elt, '10.0.0.1:25000')]
    mocked_root = create_element({'instance_h_mid': instance_h_mid, 'instance_li_mid': instance_li_mid})
    # test call with address status set in context, SILENT and different from parameter
    handler.sup_ctx.instances['10.0.0.1:25000']._state = SupvisorsInstanceStates.SILENT
    handler.write_nav_instances(mocked_root, '10.0.0.2:25000')
    assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
    assert instance_li_mid.repeat.call_args_list == [call(list(supvisors.mapper.instances.keys()))]
    assert instance_elt.attrib['class'] == 'SILENT'
    assert instance_elt.findmeld.call_args_list == [call('instance_a_mid')]
    assert instance_a_mid.attrib['class'] == 'off'
    assert instance_sp_mid.content.call_args_list == [call('10.0.0.1')]
    assert not master_sp_mid.content.called
    instance_elt.reset_all()
    mocked_root.reset_all()
    # test call with address status set in context, SILENT and identical to parameter
    handler.write_nav_instances(mocked_root, '10.0.0.1:25000')
    assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
    assert instance_li_mid.repeat.call_args_list == [call(list(supvisors.mapper.instances.keys()))]
    assert instance_elt.attrib['class'] == 'SILENT active'
    assert instance_elt.findmeld.call_args_list == [call('instance_a_mid')]
    assert instance_a_mid.attrib['class'] == 'off'
    assert instance_sp_mid.content.call_args_list == [call('10.0.0.1')]
    assert not master_sp_mid.content.called


def test_write_nav_instances_running_instance(mocker, supvisors, handler):
    """ Test the write_nav_instances method using a RUNNING instance. """
    # patch the meld elements
    instance_sp_mid = create_element()
    master_sp_mid = create_element()
    instance_a_mid = create_element({'instance_sp_mid': instance_sp_mid, 'master_sp_mid': master_sp_mid})
    instance_h_mid = create_element()
    instance_elt = create_element({'instance_a_mid': instance_a_mid})
    instance_li_mid = create_element()
    instance_li_mid.repeat.return_value = [(instance_elt, '10.0.0.1:25000')]
    mocked_root = create_element({'instance_h_mid': instance_h_mid, 'instance_li_mid': instance_li_mid})
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # loop on active states
    status = handler.sup_ctx.instances['10.0.0.1:25000']
    all_identifiers = list(supvisors.mapper.instances.keys())
    for state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
        # set context
        status._state = state
        status.state_modes.starting_jobs = False
        handler.sup_ctx.master_identifier = ''
        # test call with address status set in context, RUNNING, different from parameter and not MASTER
        mocker.patch.object(status, 'has_error', return_value=False)
        handler.write_nav_instances(mocked_root, '10.0.0.2:25000')
        assert mocked_root.findmeld.call_args_list == [call('instance_li_mid')]
        assert instance_li_mid.repeat.call_args_list == [call(all_identifiers)]
        assert instance_elt.attrib['class'] == state.name
        assert instance_elt.findmeld.call_args_list == [call('instance_a_mid')]
        assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1:25000', 'proc_instance.html')]
        assert instance_a_mid.attributes.call_args_list == [call(href='an url')]
        assert instance_a_mid.attrib['class'] == 'on'
        assert instance_sp_mid.content.call_args_list == [call('10.0.0.1')]
        assert not master_sp_mid.content.called
        instance_elt.reset_all()
        mocked_root.reset_all()
        handler.view_ctx.format_url.reset_mock()
        # test call with address status set in context, RUNNING, identical to parameter and MASTER
        # failure is added to the instance
        is_running = state == SupvisorsInstanceStates.RUNNING
        mocker.patch.object(status, 'has_error', return_value=is_running)
        status.state_modes.starting_jobs = True
        handler.sup_ctx.master_identifier = '10.0.0.1:25000'
        handler.write_nav_instances(mocked_root, '10.0.0.1:25000')
        expected = [call('instance_li_mid')] + ([call('instance_h_mid')] if is_running else [])
        assert mocked_root.findmeld.call_args_list == expected
        assert instance_li_mid.repeat.call_args_list == [call(all_identifiers)]
        assert instance_elt.attrib['class'] == state.name + ' active' + (' failure' if is_running else '') + ' master'
        assert instance_elt.findmeld.call_args_list == [call('instance_a_mid')]
        assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1:25000', 'proc_instance.html')]
        assert instance_a_mid.attributes.call_args_list == [call(href='an url')]
        assert instance_a_mid.attrib['class'] == 'blink on'
        assert instance_sp_mid.content.call_args_list == [call('10.0.0.1')]
        assert master_sp_mid.content.call_args_list == [call(MASTER_SYMBOL)]
        assert instance_h_mid.attrib['class'] == ('failure' if is_running else '')
        instance_elt.reset_all()
        mocked_root.reset_all()
        handler.view_ctx.format_url.reset_mock()


def test_write_nav_applications_initialization(supvisors, handler):
    """ Test the write_nav_applications method with Supvisors in its INITIALIZATION state. """
    supvisors.fsm.state = SupvisorsStates.INITIALIZATION
    dummy_appli = create_application('dummy_appli', supvisors)
    dummy_appli._state = ApplicationStates.RUNNING
    supvisors.starter.get_application_job_names.return_value = set()
    supvisors.stopper.get_application_job_names.return_value = set()
    # patch the meld elements
    appli_a_mid = create_element()
    appli_elt = create_element({'appli_a_mid': appli_a_mid})
    appli_li_mid = create_element()
    appli_li_mid.repeat.return_value = [(appli_elt, dummy_appli)]
    appli_h_mid = create_element()
    mocked_root = create_element({'appli_li_mid': appli_li_mid, 'appli_h_mid': appli_h_mid})
    # test call with application name different from parameter
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.write_nav_applications(mocked_root, 'dumb_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'off'
    assert handler.view_ctx.format_url.call_args_list == []
    assert appli_a_mid.attributes.call_args_list == []
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]
    assert appli_h_mid.attrib['class'] == ''
    mocked_root.reset_all()
    appli_elt.reset_all()
    # test call with application name identical to parameter and add a failure
    supvisors.starter.get_application_job_names.return_value = {'dummy_appli'}
    dummy_appli.minor_failure = True
    handler.write_nav_applications(mocked_root, 'dummy_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid'), call('appli_h_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING active failure'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'blink off'
    assert handler.view_ctx.format_url.call_args_list == []
    assert appli_a_mid.attributes.call_args_list == []
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]
    assert appli_h_mid.attrib['class'] == 'failure'


def test_write_nav_applications_operation(supvisors, handler):
    """ Test the write_nav_applications method with Supvisors in its OPERATION state. """
    supvisors.fsm.state = SupvisorsStates.OPERATION
    dummy_appli = create_application('dummy_appli', supvisors)
    dummy_appli._state = ApplicationStates.RUNNING
    dummy_appli.rules.starting_strategy = StartingStrategies.LESS_LOADED
    supvisors.starter.get_application_job_names.return_value = set()
    supvisors.stopper.get_application_job_names.return_value = set()
    # patch the meld elements
    appli_a_mid = create_element()
    appli_elt = create_element({'appli_a_mid': appli_a_mid})
    appli_li_mid = create_element()
    appli_li_mid.repeat.return_value = [(appli_elt, dummy_appli)]
    appli_h_mid = create_element()
    mocked_root = create_element({'appli_li_mid': appli_li_mid, 'appli_h_mid': appli_h_mid})
    # test call with application name different from parameter and failure
    dummy_appli.major_failure = True
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    handler.write_nav_applications(mocked_root, 'dumb_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid'), call('appli_h_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING failure'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'on'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'application.html', appname='dummy_appli',
                                                               strategy='LESS_LOADED')]
    assert appli_a_mid.attributes.call_args_list == [call(href='an url')]
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]
    assert appli_h_mid.attrib['class'] == 'failure'
    handler.view_ctx.format_url.reset_mock()
    mocked_root.reset_all()
    appli_elt.reset_all()
    # test call with application name identical to parameter
    supvisors.stopper.get_application_job_names.return_value = {'dummy_appli'}
    dummy_appli.major_failure = False
    handler.write_nav_applications(mocked_root, 'dummy_appli')
    assert mocked_root.findmeld.call_args_list == [call('appli_li_mid')]
    assert appli_elt.attrib['class'] == 'RUNNING active'
    assert appli_elt.findmeld.call_args_list == [call('appli_a_mid')]
    assert appli_a_mid.attrib['class'] == 'blink on'
    assert handler.view_ctx.format_url.call_args_list == [call('', 'application.html', appname='dummy_appli',
                                                               strategy='LESS_LOADED')]
    assert appli_a_mid.attributes.call_args_list == [call(href='an url')]
    assert appli_a_mid.content.call_args_list == [call('dummy_appli')]


def test_write_header(mocker, handler):
    """ Test the ViewHandler.write_header method. """
    mocked_software = mocker.patch.object(handler, 'write_software')
    mocked_status = mocker.patch.object(handler, 'write_status')
    mocked_options = mocker.patch.object(handler, 'write_options')
    mocked_actions = mocker.patch.object(handler, 'write_actions')
    mocked_header = create_element()
    handler.write_header(mocked_header)
    assert mocked_software.call_args_list == [call(mocked_header)]
    assert mocked_status.call_args_list == [call(mocked_header)]
    assert mocked_options.call_args_list == [call(mocked_header)]
    assert mocked_actions.call_args_list == [call(mocked_header)]


def test_write_software(mocker, supvisors, handler):
    """ Test the ViewHandler.write_software method. """
    mocked_path = mocker.patch('supvisors.web.viewimage.SoftwareIconImage.set_path')
    mocked_name = create_element()
    mocked_icon = create_element()
    mocked_card = create_element({'software_icon_mid': mocked_icon, 'software_name_mid': mocked_name})
    mocked_header = create_element({'software_card_mid': mocked_card})
    # 1. test user software name but no icon
    assert supvisors.options.software_name
    assert not supvisors.options.software_icon
    handler.write_software(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('software_card_mid')]
    assert not mocked_card.replace.called
    assert mocked_card.findmeld.call_args_list == [call('software_name_mid'), call('software_icon_mid')]
    assert mocked_name.content.call_args_list == [call('Supvisors tests')]
    assert mocked_icon.replace.call_args_list == [call('')]
    assert not mocked_path.called
    # reset mocks
    mocked_header.reset_all()
    # 2. test both user software name & icon set
    supvisors.options.software_icon = '/tmp/an_icon.png'
    handler.write_software(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('software_card_mid')]
    assert not mocked_card.replace.called
    assert mocked_card.findmeld.call_args_list == [call('software_name_mid')]
    assert mocked_name.content.call_args_list == [call('Supvisors tests')]
    assert not mocked_icon.replace.called
    assert mocked_path.call_args_list == [call('/tmp/an_icon.png')]
    # reset mocks
    mocked_header.reset_all()
    mocker.resetall()
    # 3. test no user software set
    supvisors.options.software_name = ''
    supvisors.options.software_icon = None
    handler.write_software(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('software_card_mid')]
    assert mocked_card.replace.call_args_list == [call('')]
    assert not mocked_card.findmeld.called
    assert not mocked_name.content.called
    assert not mocked_icon.replace.called
    assert not mocked_path.called


def test_write_status(handler):
    """ Test the ViewHandler.write_options method. """
    with pytest.raises(NotImplementedError):
        handler.write_status(Mock())


def test_write_options(handler):
    """ Test the ViewHandler.write_options method. """
    handler.write_options(Mock())
    # no implementation, no nothing to test
    assert True


def test_write_periods(supvisors, handler):
    """ Test the ViewHandler.write_periods method. """
    # 1. test call with period selection identical to parameter
    period_a_mid = create_element()
    period_li_elt = create_element({'period_a_mid': period_a_mid})
    period_li_mid = create_element()
    period_li_mid.repeat.return_value = [(period_li_elt, 5)]
    mocked_header = create_element({'period_li_mid': period_li_mid})
    # test call with period selection identical to parameter
    handler.view_ctx = Mock(period=5, **{'format_url.return_value': 'an url'})
    handler.write_periods(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('period_li_mid')]
    assert period_li_mid.repeat.call_args_list == [call(supvisors.options.stats_periods)]
    assert period_li_elt.findmeld.call_args_list == [call('period_a_mid')]
    assert period_li_elt.attrib['class'] == 'off active'
    assert handler.view_ctx.format_url.call_args_list == []
    assert period_a_mid.attributes.call_args_list == []
    assert period_a_mid.content.call_args_list == [call('5s')]
    mocked_header.reset_all()
    period_li_elt.reset_all()
    period_a_mid.attrib['class'] = ''
    # 2. test call with period selection different from parameter
    handler.view_ctx.period = 10.0
    handler.write_periods(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('period_li_mid')]
    assert period_li_mid.repeat.call_args_list == [call(handler.supvisors.options.stats_periods)]
    assert period_li_elt.findmeld.call_args_list == [call('period_a_mid')]
    assert period_li_elt.attrib['class'] == 'on'
    assert handler.view_ctx.format_url.call_args_list == [call('', None, period=5)]
    assert period_a_mid.attributes.call_args_list == [call(href='an url')]
    assert period_a_mid.content.call_args_list == [call('5s')]


def test_write_actions(mocker, handler):
    """ Test the ViewHandler.write_header method. """
    handler.page_name = 'dummy.html'
    handler.view_ctx = Mock(auto_refresh=True, **{'format_url.return_value': 'an url'})
    mocked_refresh = create_element()
    mocked_autorefresh = create_element()
    mocked_autorefresh.attrib['class'] = 'button'
    mocked_header = create_element({'refresh_a_mid': mocked_refresh, 'autorefresh_a_mid': mocked_autorefresh})
    # 1. test auto-refresh
    handler.write_actions(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('refresh_a_mid'), call('autorefresh_a_mid')]
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html'),
                                                          call('', 'dummy.html', auto=False)]
    assert mocked_refresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attrib['class'] == 'button active'
    # reset mocks and context
    mocker.resetall()
    mocked_header.reset_all()
    handler.view_ctx.format_url.reset_mock()
    mocked_autorefresh.attrib['class'] = 'button'
    # 2. test no auto-refresh
    handler.view_ctx.auto_refresh = False
    handler.write_actions(mocked_header)
    assert mocked_header.findmeld.call_args_list == [call('refresh_a_mid'), call('autorefresh_a_mid')]
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html'),
                                                          call('', 'dummy.html', auto=True)]
    assert mocked_refresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attributes.call_args_list == [call(href='an url')]
    assert mocked_autorefresh.attrib['class'] == 'button'


def test_write_contents(handler):
    """ Test the write_contents method. """
    with pytest.raises(NotImplementedError):
        handler.write_contents(Mock())


def test_write_global_shex(handler):
    """ Test the write_global_shex method. """
    handler.page_name = 'dummy.html'
    # add context
    expanded = bytearray.fromhex('ffff')
    shrank = bytearray.fromhex('0000')
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # build HTML structure
    expand_a_mid = create_element()
    shrink_a_mid = create_element()
    table_elt = create_element({'expand_a_mid': expand_a_mid, 'shrink_a_mid': shrink_a_mid})
    # test with fully expanded shex
    handler.write_global_shex(table_elt, 'shex', 'ffff', expanded, shrank)
    assert expand_a_mid.replace.call_args_list == [call('')]
    assert not expand_a_mid.content.called
    assert not expand_a_mid.attributes.called
    assert not shrink_a_mid.replace.called
    assert shrink_a_mid.content.call_args_list == [call(SHEX_SHRINK)]
    assert shrink_a_mid.attributes.call_args_list == [call(href='an url')]
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html', shex='0000')]
    table_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test with fully shrank shex
    handler.write_global_shex(table_elt, 'shex', '0000', expanded, shrank)
    assert not expand_a_mid.replace.called
    assert expand_a_mid.content.call_args_list == [call(SHEX_EXPAND)]
    assert expand_a_mid.attributes.call_args_list == [call(href='an url')]
    assert shrink_a_mid.replace.call_args_list == [call('')]
    assert not shrink_a_mid.content.called
    assert not shrink_a_mid.attributes.called
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html', shex='ffff')]
    table_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test with fully mixed shex
    handler.write_global_shex(table_elt, 'shex', '1234', expanded, shrank)
    assert not expand_a_mid.replace.called
    assert expand_a_mid.content.call_args_list == [call(SHEX_EXPAND)]
    assert expand_a_mid.attributes.call_args_list == [call(href='an url')]
    assert not shrink_a_mid.replace.called
    assert shrink_a_mid.content.call_args_list == [call(SHEX_SHRINK)]
    assert shrink_a_mid.attributes.call_args_list == [call(href='an url')]
    assert handler.view_ctx.format_url.call_args_list == [call('', 'dummy.html', shex='ffff'),
                                                          call('', 'dummy.html', shex='0000')]


def test_write_common_process_cpu(supvisors, handler):
    """ Test the write_common_process_cpu method. """
    # patch the view context
    handler.view_ctx = Mock(process_name='dummy_proc', identifier='10.0.0.1',
                            **{'format_url.return_value': 'an url'})
    # patch the meld elements
    pcpu_a_mid = create_element()
    pcpu_td_mid = create_element()
    tr_elt = create_element({'pcpu_a_mid': pcpu_a_mid, 'pcpu_td_mid': pcpu_td_mid})
    # test with no stats
    info = {'proc_stats': None}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not pcpu_a_mid.deparent.called
    assert pcpu_a_mid.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not pcpu_a_mid.content.called
    # reset context
    tr_elt.findmeld.reset_mock()
    pcpu_a_mid.replace.reset_mock()
    # test with empty stats
    info = {'proc_stats': Mock(cpu=[])}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not pcpu_a_mid.deparent.called
    assert pcpu_a_mid.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not pcpu_a_mid.content.called
    tr_elt.reset_all()
    # test with filled stats on selected process, irix mode
    supvisors.options.stats_irix_mode = True
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.1', 'proc_stats': Mock(cpu=[10, 20]), 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not pcpu_a_mid.deparent.called
    assert not pcpu_a_mid.replace.called
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname=None, ident='10.0.0.1')]
    assert pcpu_a_mid.attrib['class'] == 'button on active'
    assert pcpu_a_mid.content.call_args_list == [call('20.00')]
    # reset context
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test with filled stats on not selected process, solaris mode
    supvisors.options.stats_irix_mode = False
    info = {'namespec': 'dummy', 'identifier': '10.0.0.1', 'proc_stats': Mock(cpu=[10, 20, 30]), 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not pcpu_a_mid.deparent.called
    assert not pcpu_a_mid.replace.called
    assert pcpu_a_mid.content.call_args_list == [call('15.00')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname='dummy', ident='10.0.0.1')]
    assert pcpu_a_mid.attributes.call_args_list == [call(href='an url')]
    assert pcpu_a_mid.attrib['class'] == 'button on'
    # reset context
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test with filled stats on application (so non process), solaris mode
    handler.supvisors.options.stats_irix_mode = False
    info = {'namespec': None, 'ident': '10.0.0.1', 'proc_stats': Mock(cpu=[10, 20, 30]), 'nb_cores': 2}
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_a_mid')]
    assert not pcpu_a_mid.deparent.called
    assert pcpu_a_mid.replace.call_args_list == [call('15.00')]
    assert not pcpu_a_mid.content.called
    assert not handler.view_ctx.format_url.called
    assert not pcpu_a_mid.attributes.called
    assert pcpu_a_mid.attrib['class'] == ''
    # reset context
    tr_elt.reset_all()
    # test with statistics disabled
    handler.has_process_statistics = False
    handler.write_common_process_cpu(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pcpu_td_mid')]
    assert pcpu_td_mid.deparent.call_args_list == [call()]
    assert not pcpu_a_mid.replace.called
    assert not pcpu_a_mid.content.called
    assert not handler.view_ctx.format_url.called
    assert not pcpu_a_mid.attributes.called


def test_write_common_process_mem(handler):
    """ Test the write_common_process_mem method. """
    # patch the view context
    handler.view_ctx = Mock(process_name='dummy_proc', identifier='10.0.0.2',
                            **{'format_url.return_value': 'an url'})
    # patch the meld elements
    pmem_a_mid = create_element()
    pmem_td_mid = create_element()
    tr_elt = create_element({'pmem_td_mid': pmem_td_mid, 'pmem_a_mid': pmem_a_mid})
    # test with no stats
    info = {'proc_stats': None}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not pmem_a_mid.deparent.called
    assert pmem_a_mid.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not pmem_a_mid.content.called
    # reset context
    tr_elt.reset_all()
    # test with empty stats
    info = {'proc_stats': Mock(mem=[])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not pmem_a_mid.deparent.called
    assert pmem_a_mid.replace.call_args_list == [call('--')]
    assert not handler.view_ctx.format_url.called
    assert not pmem_a_mid.content.called
    # reset context
    tr_elt.reset_all()
    # test with filled stats on selected process
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.2', 'proc_stats': Mock(mem=[10, 20])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not pmem_a_mid.deparent.called
    assert not pmem_a_mid.replace.called
    assert pmem_a_mid.content.call_args_list == [call('20.00')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname=None, ident='10.0.0.2')]
    assert pmem_a_mid.attrib['class'] == 'button on active'
    # reset context
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test with filled stats on not selected process
    info = {'namespec': 'dummy', 'identifier': '10.0.0.2', 'proc_stats': Mock(mem=[10, 20, 30])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not pmem_a_mid.deparent.called
    assert not pmem_a_mid.replace.called
    assert pmem_a_mid.content.call_args_list == [call('30.00')]
    assert handler.view_ctx.format_url.call_args_list == [call('', None, processname='dummy', ident='10.0.0.2')]
    assert pmem_a_mid.attributes.call_args_list == [call(href='an url')]
    assert pmem_a_mid.attrib['class'] == 'button on'
    # reset context
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test with filled stats on application (so non process)
    info = {'namespec': None, 'identifier': '10.0.0.2', 'proc_stats': Mock(mem=[10, 20, 30])}
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_a_mid')]
    assert not pmem_a_mid.deparent.called
    assert pmem_a_mid.replace.call_args_list == [call('30.00')]
    assert not pmem_a_mid.content.called
    assert not handler.view_ctx.format_url.called
    assert not pmem_a_mid.attributes.called
    assert pmem_a_mid.attrib['class'] == ''
    # reset context
    tr_elt.reset_all()
    # test with statistics disabled
    handler.has_process_statistics = False
    handler.write_common_process_mem(tr_elt, info)
    assert tr_elt.findmeld.call_args_list == [call('pmem_td_mid')]
    assert pmem_td_mid.deparent.call_args_list == [call()]
    assert not pmem_a_mid.replace.called
    assert not pmem_a_mid.content.called
    assert not handler.view_ctx.format_url.called
    assert not pmem_a_mid.attributes.called


def test_write_process_start_button(mocker, handler):
    """ Test the write_process_start_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call redirection when program is disabled
    info = {'namespec': 'dummy_proc', 'statecode': ProcessStates.STOPPED, 'startable': False}
    handler.write_process_start_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'start_a_mid', '', 'My Page', 'start', 'dummy_proc', False)]
    mocked_button.reset_mock()
    # test call redirection when program is enabled
    info['startable'] = True
    handler.write_process_start_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'start_a_mid', '', 'My Page', 'start', 'dummy_proc', True)]


def test_write_process_stop_button(mocker, handler):
    """ Test the write_process_stop_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call redirection
    info = {'namespec': 'dummy_proc', 'statecode': ProcessStates.STARTING, 'stoppable': True}
    handler.write_process_stop_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'stop_a_mid', '', 'My Page', 'stop', 'dummy_proc', True)]


def test_write_process_restart_button(mocker, handler):
    """ Test the write_process_restart_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call redirection when program is disabled
    info = {'namespec': 'dummy_proc', 'statecode': ProcessStates.RUNNING, 'startable': False}
    handler.write_process_restart_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'restart_a_mid', '', 'My Page', 'restart', 'dummy_proc', False)]
    mocked_button.reset_mock()
    # test call redirection when program is enabled
    info['startable'] = True
    handler.write_process_restart_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'restart_a_mid', '', 'My Page', 'restart', 'dummy_proc', True)]


def test_write_process_clear_button(mocker, handler):
    """ Test the write_process_clear_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection with no stdout/stderr output configured
    info = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1',
            'has_stdout': False, 'has_stderr': False}
    handler.write_process_clear_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'clear_a_mid', '10.0.0.1', 'My Page', 'clearlog',
                                                 'dummy_application:dummy_process_1', False)]
    mocked_button.reset_mock()
    # test call indirection with one of stdout/stderr output configured
    info['has_stdout'] = True
    handler.write_process_clear_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'clear_a_mid', '10.0.0.1', 'My Page', 'clearlog',
                                                 'dummy_application:dummy_process_1', True)]
    mocked_button.reset_mock()
    # test call indirection with both stdout/stderr output configured
    info['has_stderr'] = True
    handler.write_process_clear_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'clear_a_mid', '10.0.0.1', 'My Page', 'clearlog',
                                                 'dummy_application:dummy_process_1', True)]
    mocked_button.reset_mock()


def test_write_process_stdout_button(mocker, handler):
    """ Test the write_process_stdout_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection with no stdout output configured
    info = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1', 'has_stdout': False}
    handler.write_process_stdout_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'tailout_a_mid', '10.0.0.1',
                                                 'logtail/dummy_application%3Adummy_process_1',
                                                 '', 'dummy_application:dummy_process_1', False)]
    mocked_button.reset_mock()
    # test call indirection with stdout output configured
    info = {'namespec': 'dummy_application:dummy_process_2', 'identifier': '', 'has_stdout': True}
    handler.write_process_stdout_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'tailout_a_mid', '',
                                                 'logtail/dummy_application%3Adummy_process_2',
                                                 '', 'dummy_application:dummy_process_2', True)]


def test_write_process_stderr_button(mocker, handler):
    """ Test the write_process_stderr_button method. """
    mocked_button = mocker.patch('supvisors.web.viewhandler.ViewHandler._write_process_button')
    handler.page_name = 'My Page'
    # test call indirection with no stderr output configured
    info = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1', 'has_stderr': False}
    handler.write_process_stderr_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'tailerr_a_mid', '10.0.0.1',
                                                 'logtail/dummy_application%3Adummy_process_1/stderr',
                                                 '', 'dummy_application:dummy_process_1', False)]
    mocked_button.reset_mock()
    # test call indirection with stderr output configured
    info = {'namespec': 'dummy_application:dummy_process_2', 'identifier': '', 'has_stderr': True}
    handler.write_process_stderr_button('elt', info)
    assert mocked_button.call_args_list == [call('elt', 'tailerr_a_mid', '',
                                                 'logtail/dummy_application%3Adummy_process_2/stderr',
                                                 '', 'dummy_application:dummy_process_2', True)]


def test_write_process_button(handler):
    """ Test the _write_process_button method. """
    # patch the view context
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    cell_elt = Mock(attrib={'class': ''})
    tr_elt = Mock(**{'findmeld.return_value': cell_elt})
    # test with process state not in expected list
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc', False)
    assert tr_elt.findmeld.call_args_list == [call('meld_id')]
    assert cell_elt.attrib['class'] == 'button off'
    assert not cell_elt.attributes.called
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    del cell_elt.attrib['class']
    # test with filled stats on selected process
    handler._write_process_button(tr_elt, 'meld_id', '10.0.0.1', 'index.html', 'action', 'dummy_proc', True)
    assert tr_elt.findmeld.call_args_list == [call('meld_id')]
    assert cell_elt.attrib['class'] == 'button on'
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'index.html', action='action',
                                                               namespec='dummy_proc')]
    assert cell_elt.attributes.call_args_list == [call(href='an url')]
    assert not cell_elt.content.called
    tr_elt.findmeld.reset_mock()
    handler.view_ctx.format_url.reset_mock()
    cell_elt.attributes.reset_mock()
    del cell_elt.attrib['class']


def test_write_common_process_table(handler):
    """ Test the write_common_process_table method. """
    mem_head_elt = create_element()
    mem_foot_elt = create_element()
    mem_total_elt = create_element()
    cpu_head_elt = create_element()
    cpu_foot_elt = create_element()
    cpu_total_elt = create_element()
    root = create_element({'mem_head_th_mid': mem_head_elt, 'cpu_head_th_mid': cpu_head_elt,
                           'mem_foot_th_mid': mem_foot_elt, 'cpu_foot_th_mid': cpu_foot_elt,
                           'mem_total_th_mid': mem_total_elt, 'cpu_total_th_mid': cpu_total_elt})
    # test with statistics enabled
    handler.has_process_statistics = True
    handler.write_common_process_table(root)
    assert not root.findmeld.called
    assert not mem_head_elt.deparent.called
    assert not mem_foot_elt.deparent.called
    assert not cpu_head_elt.deparent.called
    assert not cpu_foot_elt.deparent.called
    # test with statistics enabled
    handler.has_process_statistics = False
    handler.write_common_process_table(root)
    assert root.findmeld.call_args_list == [call('mem_head_th_mid'), call('cpu_head_th_mid'),
                                            call('mem_foot_th_mid'), call('cpu_foot_th_mid'),
                                            call('mem_total_th_mid'), call('cpu_total_th_mid')]
    assert mem_head_elt.deparent.call_args_list == [call()]
    assert mem_foot_elt.deparent.call_args_list == [call()]
    assert cpu_head_elt.deparent.call_args_list == [call()]
    assert cpu_foot_elt.deparent.call_args_list == [call()]


def test_write_common_state(handler):
    """ Test the write_common_state method. """
    # patch the meld elements
    state_span_mid = create_element()
    state_td_mid = create_element({'state_span_mid': state_span_mid})
    desc_td_mid = create_element()
    tr_elt = create_element({'state_td_mid': state_td_mid, 'desc_td_mid': desc_td_mid})
    # test call on process that has never crashed
    param = {'expected_load': 35, 'statename': 'exited', 'gravity': 'exited', 'disabled': True,
             'has_crashed': False, 'description': 'something'}
    handler.write_common_state(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('state_td_mid'), call('desc_td_mid')]
    assert state_td_mid.findmeld.call_args_list == [call('state_span_mid')]
    assert state_td_mid.attrib['class'] == 'exited disabled'
    assert state_span_mid.content.call_args_list == [call('exited')]
    assert state_span_mid.attrib['class'] == ''
    assert desc_td_mid.content.call_args_list == [call('something')]
    tr_elt.reset_all()
    # test call on process that has ever crashed, and multiple instances running
    param.update({'gravity': 'fatal', 'has_crashed': True, 'disabled': False, 'running_identifiers': [0, 0]})
    handler.write_common_state(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('state_td_mid'), call('desc_td_mid')]
    assert state_td_mid.findmeld.call_args_list == [call('state_span_mid')]
    assert state_td_mid.attrib['class'] == 'fatal crashed'
    assert state_span_mid.content.call_args_list == [call('exited')]
    assert state_span_mid.attrib['class'] == 'blink'
    assert desc_td_mid.content.call_args_list == [call('something')]


def test_write_common_statistics(mocker, handler):
    """ Test the write_common_process_status method. """
    mocked_mem = mocker.patch.object(handler, 'write_common_process_mem')
    mocked_cpu = mocker.patch.object(handler, 'write_common_process_cpu')
    # patch the meld elements
    load_elt = Mock(attrib={'class': ''})
    tr_elt = create_element({'load_td_mid': load_elt})
    # test call on process that never crashed
    param = {'expected_load': 35, 'statename': 'exited', 'gravity': 'exited', 'disabled': True,
             'has_crashed': False, 'description': 'something'}
    handler.write_common_statistics(tr_elt, param)
    assert tr_elt.findmeld.call_args_list == [call('load_td_mid')]
    assert load_elt.content.call_args_list == [call('35')]
    assert mocked_cpu.call_args_list == [call(tr_elt, param)]
    assert mocked_mem.call_args_list == [call(tr_elt, param)]


def test_write_common_process_status(mocker, handler):
    """ Test the write_common_process_status method. """
    mocked_stderr = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_stderr_button')
    mocked_stdout = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_stdout_button')
    mocked_clear = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_clear_button')
    mocked_restart = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_restart_button')
    mocked_stop = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_stop_button')
    mocked_start = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_start_button')
    mocked_state = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_common_state')
    mocked_stats = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_common_statistics')
    # patch the view context
    handler.view_ctx = Mock(**{'format_url.return_value': 'an url'})
    # patch the meld elements
    name_a_elt = create_element()
    name_td_elt = create_element({'name_a_mid': name_a_elt})
    tr_elt = create_element({'name_td_mid': name_td_elt})
    # test call on selected process having a stdout_logfile
    param = {'namespec': 'dummy_application:dummy_process_1', 'identifier': '10.0.0.1',
             'process_name': 'dummy_process_1', 'has_stdout': True}
    handler.write_common_process_status(tr_elt, param)
    assert mocked_state.call_args_list == [call(tr_elt, param)]
    assert mocked_stats.call_args_list == [call(tr_elt, param)]
    assert not name_td_elt.content.called
    assert name_a_elt.content.call_args_list == [call('\u21B3 dummy_process_1')]
    assert handler.view_ctx.format_url.call_args_list == [call('10.0.0.1', 'tail.html',
                                                               processname='dummy_application:dummy_process_1',
                                                               limit=1024)]
    assert name_a_elt.attributes.call_args_list == [call(href='an url', target="_blank")]
    assert mocked_start.call_args_list == [call(tr_elt, param)]
    assert mocked_stop.call_args_list == [call(tr_elt, param)]
    assert mocked_restart.call_args_list == [call(tr_elt, param)]
    assert mocked_clear.call_args_list == [call(tr_elt, param)]
    assert mocked_stdout.call_args_list == [call(tr_elt, param)]
    assert mocked_stderr.call_args_list == [call(tr_elt, param)]
    mocker.resetall()
    tr_elt.reset_all()
    handler.view_ctx.format_url.reset_mock()
    # test call on selected process NOT having a stdout_logfile
    param = {'namespec': 'dummy_application:dummy_process_2', 'identifier': '10.0.0.1',
             'process_name': 'dummy_process_1', 'has_stdout': False}
    handler.write_common_process_status(tr_elt, param)
    assert mocked_state.call_args_list == [call(tr_elt, param)]
    assert mocked_stats.call_args_list == [call(tr_elt, param)]
    assert name_td_elt.content.call_args_list == [call('\u21B3 dummy_process_1')]
    assert not name_a_elt.content.called
    assert not handler.view_ctx.format_url.called
    assert not name_a_elt.attributes.called
    assert mocked_start.call_args_list == [call(tr_elt, param)]
    assert mocked_stop.call_args_list == [call(tr_elt, param)]
    assert mocked_restart.call_args_list == [call(tr_elt, param)]
    assert mocked_clear.call_args_list == [call(tr_elt, param)]
    assert mocked_stdout.call_args_list == [call(tr_elt, param)]
    assert mocked_stderr.call_args_list == [call(tr_elt, param)]


def test_write_detailed_process_cpu(mocker, supvisors, handler):
    """ Test the write_detailed_process_cpu method. """
    mocked_common = mocker.patch.object(handler, '_write_common_detailed_statistics')
    # create fake stats
    proc_stats = Mock(times=[1, 2, 3], cpu=[10, 16, 13])
    # context
    stats_elt = create_element()
    supvisors.options.stats_irix_mode = True
    # test call with no stats
    assert not handler.write_detailed_process_cpu(stats_elt, None, 4)
    # test call with empty stats
    for mode in [True, False]:
        supvisors.options.stats_irix_mode = mode
        assert handler.write_detailed_process_cpu(stats_elt, Mock(cpu=[], times=[]), 4)
        assert mocked_common.call_args_list == [call(stats_elt, [], [],
                                                     'pcpuval_td_mid', 'pcpuavg_td_mid',
                                                     'pcpuslope_td_mid', 'pcpudev_td_mid')]
        mocked_common.reset_mock()
    # test call with irix mode
    supvisors.options.stats_irix_mode = True
    assert handler.write_detailed_process_cpu(stats_elt, proc_stats, 4)
    assert mocked_common.call_args_list == [call(stats_elt, [10, 16, 13], [1, 2, 3],
                                                 'pcpuval_td_mid', 'pcpuavg_td_mid',
                                                 'pcpuslope_td_mid', 'pcpudev_td_mid')]
    mocked_common.reset_mock()
    # test call with solaris mode
    supvisors.options.stats_irix_mode = False
    assert handler.write_detailed_process_cpu(stats_elt, proc_stats, 4)
    assert mocked_common.call_args_list == [call(stats_elt, [2.5, 4, 3.25], [1, 2, 3],
                                                 'pcpuval_td_mid', 'pcpuavg_td_mid',
                                                 'pcpuslope_td_mid', 'pcpudev_td_mid')]


def test_write_detailed_process_mem(mocker, handler):
    """ Test the write_detailed_process_mem method. """
    mocked_common = mocker.patch.object(handler, '_write_common_detailed_statistics')
    # create fake stats
    proc_stats = Mock(times=[1, 2, 3], mem=[20, 32, 32])
    # context
    stats_elt = create_element()
    # test call with no stats
    assert not handler.write_detailed_process_mem(stats_elt, None)
    # test call with empty stats
    assert handler.write_detailed_process_mem(stats_elt, Mock(mem=[], times=[]))
    assert mocked_common.call_args_list == [call(stats_elt, [], [],
                                                 'pmemval_td_mid', 'pmemavg_td_mid',
                                                 'pmemslope_td_mid', 'pmemdev_td_mid')]
    mocked_common.reset_mock()
    # test call stats
    assert handler.write_detailed_process_mem(stats_elt, proc_stats)
    assert mocked_common.call_args_list == [call(stats_elt, [20, 32, 32], [1, 2, 3],
                                                 'pmemval_td_mid', 'pmemavg_td_mid',
                                                 'pmemslope_td_mid', 'pmemdev_td_mid')]


def test_write_common_detailed_statistics(mocker, handler):
    """ Test the _write_common_detailed_statistics method. """
    mocked_class = mocker.patch.object(handler, 'set_slope_class')
    mocked_stats = mocker.patch('supvisors.web.viewhandler.get_stats',
                                side_effect=[(10.231, None, (None, 2), None), (8.999, 2, (-1.1, 4), 5.72)])
    handler.view_ctx = Mock(period=10)
    # replace root structure
    mocked_val_mid = create_element()
    mocked_avg_mid = create_element()
    mocked_slope_mid = create_element()
    mocked_dev_mid = create_element()
    mocked_tr = create_element({'val_mid': mocked_val_mid, 'avg_mid': mocked_avg_mid,
                                'slope_mid': mocked_slope_mid, 'dev_mid': mocked_dev_mid})
    # in first call, test empty stats
    handler._write_common_detailed_statistics(mocked_tr, [], [],
                                              'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
    assert not mocked_tr.findmeld.called
    assert not mocked_stats.called
    assert not mocked_class.called
    assert not mocked_val_mid.called
    assert not mocked_avg_mid.called
    assert not mocked_slope_mid.called
    assert not mocked_dev_mid.called
    # in second call, test no rate, slope and standard deviation
    handler._write_common_detailed_statistics(mocked_tr, [1.523, 2.456], [1, 2],
                                              'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
    assert mocked_tr.findmeld.call_args_list == [call('val_mid'), call('avg_mid')]
    assert mocked_stats.call_args_list == [call([1, 2], [1.523, 2.456])]
    assert not mocked_class.called
    assert mocked_val_mid.content.call_args_list == [call('2.46')]
    assert mocked_avg_mid.content.call_args_list == [call('10.23')]
    assert not mocked_slope_mid.called
    assert not mocked_dev_mid.called
    mocker.resetall()
    mocked_tr.reset_all()
    # in third call, test no rate, slope and standard deviation
    handler._write_common_detailed_statistics(mocked_tr, [1.523, 2.456], [1, 2],
                                              'val_mid', 'avg_mid', 'slope_mid', 'dev_mid')
    assert mocked_stats.call_args_list == [call([1, 2], [1.523, 2.456])]
    assert mocked_class.call_args_list == [call(mocked_val_mid, 2)]
    assert mocked_tr.findmeld.call_args_list == [call('val_mid'), call('avg_mid'), call('slope_mid'), call('dev_mid')]
    assert mocked_val_mid.content.call_args_list == [call('2.46')]
    assert mocked_avg_mid.content.call_args_list == [call('9.00')]
    assert mocked_slope_mid.content.call_args_list == [call('-11.00')]  # impact of PERIOD
    assert mocked_dev_mid.content.call_args_list == [call('5.72')]


def test_write_process_plots_no_plot(mocker, handler):
    """ Test the write_process_plots method in the event of matplotlib import error. """
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocker.patch.dict('sys.modules', {'supvisors.plot': None})
    # test call
    assert not handler.write_process_plots([])
    # test that plot methods are not called
    assert not mocked_export.called


def test_write_process_plots(mocker, supvisors, handler):
    """ Test the write_process_plots method. """
    # skip test if matplotlib is not installed
    pytest.importorskip('matplotlib', reason='cannot test as optional matplotlib is not installed')
    # get patches
    mocked_export = mocker.patch('supvisors.plot.StatisticsPlot.export_image')
    mocked_time = mocker.patch('supvisors.plot.StatisticsPlot.add_timeline')
    mocked_plot = mocker.patch('supvisors.plot.StatisticsPlot.add_plot')
    # test call with dummy stats
    proc_stats = Mock(times=[1, 2, 3], cpu=[10, 16, 24], mem=[20, 32, 32])
    assert handler.write_process_plots(proc_stats)
    assert mocked_time.call_args_list == [call([1, 2, 3]), call([1, 2, 3])]
    assert mocked_plot.call_args_list == [call('CPU', '%', [10, 16, 24]), call('MEM', '%', [20, 32, 32])]
    assert mocked_export.call_args_list == [call(process_cpu_img), call(process_mem_img)]


def test_write_process_statistics(mocker, handler):
    """ Test the write_process_statistics method. """
    mocked_plots = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_process_plots', return_value=True)
    mocked_mem = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_detailed_process_mem', return_value=False)
    mocked_cpu = mocker.patch('supvisors.web.viewhandler.ViewHandler.write_detailed_process_cpu', return_value=False)
    # patch the view context
    handler.view_ctx = Mock(parameters={PROCESS: None})
    # patch the meld elements
    process_td_mid = create_element()
    node_td_mid = create_element()
    ipaddress_td_mid = create_element()
    cpuimage_fig_mid = create_element()
    memimage_fig_mid = create_element()
    stats_elt = create_element({'process_td_mid': process_td_mid, 'node_td_mid': node_td_mid,
                                'ipaddress_td_mid': ipaddress_td_mid,
                                'cpuimage_fig_mid': cpuimage_fig_mid, 'memimage_fig_mid': memimage_fig_mid})
    root_elt = create_element({'pstats_div_mid': stats_elt})
    # test call with no namespec selection
    info = {}
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.replace.call_args_list == [call('')]
    assert not stats_elt.findmeld.called
    assert not mocked_cpu.called
    assert not mocked_mem.called
    assert not process_td_mid.content.called
    assert not node_td_mid.content.called
    assert not ipaddress_td_mid.content.called
    assert not cpuimage_fig_mid.replace.called
    assert not memimage_fig_mid.replace.called
    assert not mocked_plots.called
    root_elt.reset_all()
    # test call with namespec selection and no stats found
    info = {'namespec': 'dummy_proc', 'identifier': '10.0.0.1:25000', 'proc_stats': 'dummy_stats', 'nb_cores': 8}
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert not stats_elt.replace.called
    assert not stats_elt.findmeld.called
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert not process_td_mid.content.called
    assert not node_td_mid.content.called
    assert not ipaddress_td_mid.content.called
    assert not cpuimage_fig_mid.replace.called
    assert not memimage_fig_mid.replace.called
    assert not mocked_plots.called
    root_elt.reset_all()
    mocker.resetall()
    # test call with namespec selection and stats found
    mocked_cpu.return_value = True
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.findmeld.call_args_list == [call('process_td_mid'), call('node_td_mid'), call('ipaddress_td_mid')]
    assert not stats_elt.replace.called
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert process_td_mid.content.call_args_list == [call('dummy_proc')]
    assert node_td_mid.content.call_args_list == [call('10.0.0.1')]
    assert ipaddress_td_mid.content.call_args_list == [call('10.0.0.1')]
    assert not cpuimage_fig_mid.replace.called
    assert not memimage_fig_mid.replace.called
    assert mocked_plots.call_args_list == [call('dummy_stats')]
    root_elt.reset_all()
    mocker.resetall()
    # test again with matplotlib import failure
    mocked_plots.return_value = False
    handler.write_process_statistics(root_elt, info)
    assert root_elt.findmeld.call_args_list == [call('pstats_div_mid')]
    assert stats_elt.findmeld.call_args_list == [call('process_td_mid'), call('node_td_mid'), call('ipaddress_td_mid'),
                                                 call('cpuimage_fig_mid'), call('memimage_fig_mid')]
    assert not stats_elt.replace.called
    assert mocked_cpu.call_args_list == [call(stats_elt, 'dummy_stats', 8)]
    assert mocked_mem.call_args_list == [call(stats_elt, 'dummy_stats')]
    assert process_td_mid.content.call_args_list == [call('dummy_proc')]
    assert node_td_mid.content.call_args_list == [call('10.0.0.1')]
    assert ipaddress_td_mid.content.call_args_list == [call('10.0.0.1')]
    assert cpuimage_fig_mid.replace.call_args_list == [call('')]
    assert memimage_fig_mid.replace.call_args_list == [call('')]
    assert mocked_plots.call_args_list == [call('dummy_stats')]


def test_handle_action(handler):
    """ Test the handle_action method. """
    handler.view_ctx = Mock(namespec='dummy_proc', action=None)
    handler.callback = None
    handler.make_callback = Mock(return_value=lambda: NOT_DONE_YET)
    # test no action requested
    assert not handler.handle_action()
    assert not handler.make_callback.called
    # test no action in progress
    handler.view_ctx.action = 'test'
    assert handler.handle_action() == NOT_DONE_YET
    assert handler.make_callback.call_args_list == [call('dummy_proc', 'test')]
    handler.make_callback.reset_mock()
    # test action in progress
    assert handler.handle_action() == NOT_DONE_YET
    assert not handler.make_callback.called
    # test action completed
    handler.callback = None
    handler.make_callback = Mock(return_value=lambda: 'a message')
    assert not handler.handle_action()
    assert handler.make_callback.call_args_list == [call('dummy_proc', 'test')]
    assert handler.view_ctx.store_message == ('info', 'a message')


def test_make_callback(handler):
    """ Test the make_callback method. """
    with pytest.raises(NotImplementedError):
        handler.make_callback('dummy_namespec', 'dummy_action')


def test_multicall_rpc_action(mocker, handler):
    """ Test the multicall_rpc_action method. """
    mocked_rpc = mocker.patch('supvisors.web.viewhandler.generic_rpc', return_value='a deferred result')
    multicall = [{'methodName': 'supervisor.stopProcessGroup', 'params': ['dummy_proc']},
                 {'methodName': 'supervisor.startProcessGroup', 'params': ['dummy_proc', False]}]
    assert handler.multicall_rpc_action(multicall, 'successful') == 'a deferred result'
    assert mocked_rpc.call_args_list == [call(handler.supvisors.supervisor_data.system_rpc_interface,
                                              'multicall', (multicall,), 'successful')]


def test_supervisor_rpc_action(mocker, handler):
    """ Test the supervisor_rpc_action method. """
    mocked_rpc = mocker.patch('supvisors.web.viewhandler.generic_rpc', return_value='a deferred result')
    assert handler.supervisor_rpc_action('startProcess', ('dummy_proc', True), 'successful') == 'a deferred result'
    assert mocked_rpc.call_args_list == [call(handler.supvisors.supervisor_data.supervisor_rpc_interface,
                                              'startProcess', ('dummy_proc', True), 'successful')]


def test_supvisors_rpc_action(mocker, handler):
    """ Test the supvisors_rpc_action method. """
    mocked_rpc = mocker.patch('supvisors.web.viewhandler.generic_rpc', return_value='a deferred result')
    assert handler.supvisors_rpc_action('start_process', (1, 'dummy_proc', True), 'successful') == 'a deferred result'
    assert mocked_rpc.call_args_list == [call(handler.supvisors.supervisor_data.supvisors_rpc_interface,
                                              'start_process', (1, 'dummy_proc', True), 'successful')]


def test_set_slope_class():
    """ Test the set_slope_class method. """
    elt = Mock(attrib={})
    # test with values around 0
    ViewHandler.set_slope_class(elt, 0)
    assert elt.attrib['class'] == 'stable'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, 0.0049)
    assert elt.attrib['class'] == 'stable'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, -0.0049)
    assert elt.attrib['class'] == 'stable'
    del elt.attrib['class']
    # test with values around greater than 0 but not around 0
    ViewHandler.set_slope_class(elt, 0.005)
    assert elt.attrib['class'] == 'increase'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, 10)
    assert elt.attrib['class'] == 'increase'
    del elt.attrib['class']
    # test with values around lower than 0 but not around 0
    ViewHandler.set_slope_class(elt, -0.005)
    assert elt.attrib['class'] == 'decrease'
    del elt.attrib['class']
    ViewHandler.set_slope_class(elt, -10)
    assert elt.attrib['class'] == 'decrease'
