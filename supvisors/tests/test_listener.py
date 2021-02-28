#!/usr/bin/python
# -*- coding: utf-8 -*-

# ======================================================================
# Copyright 2017 Julien LE CLEACH
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

import sys
import unittest

from unittest.mock import call, patch, Mock, DEFAULT
from supervisor.events import *

from supvisors.tests.base import MockedSupvisors


class ListenerTest(unittest.TestCase):
    """ Test case for the listener module. """

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.supvisors = MockedSupvisors()

    @patch.dict('sys.modules', {'supvisors.statscollector': None})
    def test_creation_no_collector(self):
        """ Test the values set at construction. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # check attributes
        self.assertIs(self.supvisors, listener.supvisors)
        self.assertIsNone(listener.collector)
        self.assertEqual('127.0.0.1', listener.address)
        self.assertIsNone(listener.publisher)
        self.assertIsNone(listener.main_loop)
        # test that callbacks are set in Supervisor
        self.assertIn((SupervisorRunningEvent, listener.on_running), callbacks)
        self.assertIn((SupervisorStoppingEvent, listener.on_stopping), callbacks)
        self.assertIn((ProcessStateEvent, listener.on_process), callbacks)
        self.assertIn((Tick5Event, listener.on_tick), callbacks)
        self.assertIn((RemoteCommunicationEvent, listener.on_remote_event), callbacks)

    @patch.dict('sys.modules',
                **{'supvisors.statscollector': Mock(
                    **{'instant_statistics.side_effect': lambda: True})})
    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # check attributes
        self.assertIs(self.supvisors, listener.supvisors)
        self.assertTrue(listener.collector())
        self.assertEqual('127.0.0.1', listener.address)
        self.assertIsNone(listener.publisher)
        self.assertIsNone(listener.main_loop)
        # test that callbacks are set in Supervisor
        self.assertIn((SupervisorRunningEvent, listener.on_running), callbacks)
        self.assertIn((SupervisorStoppingEvent, listener.on_stopping), callbacks)
        self.assertIn((ProcessStateEvent, listener.on_process), callbacks)
        self.assertIn((Tick5Event, listener.on_tick), callbacks)
        self.assertIn((RemoteCommunicationEvent, listener.on_remote_event), callbacks)

    def test_on_running(self):
        """ Test the reception of a Supervisor RUNNING event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        ref_publisher = listener.publisher
        ref_main_loop = listener.main_loop
        with patch.object(self.supvisors.info_source, 'replace_default_handler') as mocked_infosource:
            with patch('supvisors.listener.SupervisorZmq') as mocked_zmq:
                with patch('supvisors.listener.SupvisorsMainLoop') as mocked_loop:
                    listener.on_running('')
                    # test attributes and calls
                    self.assertTrue(mocked_infosource.called)
                    self.assertTrue(mocked_zmq.called)
                    self.assertIsNot(ref_publisher, listener.publisher)
                    self.assertTrue(mocked_loop.called)
                    self.assertIsNot(ref_main_loop, listener.main_loop)
                    self.assertTrue(listener.main_loop.start.called)

    def test_on_stopping(self):
        """ Test the reception of a Supervisor STOPPING event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # create a main_loop patch
        listener.main_loop = Mock(**{'stop.return_value': None})
        with patch.object(self.supvisors.info_source, 'close_httpservers') as mocked_infosource:
            # 1. test with unmarked logger, i.e. meant to be the supervisor logger
            listener.on_stopping('')
            self.assertEqual([], callbacks)
            self.assertTrue(mocked_infosource.called)
            self.assertTrue(listener.main_loop.stop.called)
            self.assertTrue(self.supvisors.zmq.close.called)
            self.assertFalse(self.supvisors.logger.close.called)
            # reset mocks
            mocked_infosource.reset_mock()
            listener.main_loop.stop.reset_mock()
            self.supvisors.zmq.close.reset_mock()
            # 2. test with marked logger, i.e. meant to be the Supvisors logger
            listener.logger.SUPVISORS = None
            listener.on_stopping('')
            self.assertEqual([], callbacks)
            self.assertTrue(mocked_infosource.called)
            self.assertTrue(listener.main_loop.stop.called)
            self.assertTrue(self.supvisors.zmq.close.called)
            self.assertTrue(self.supvisors.logger.close.called)

    @patch('supvisors.listener.time.time', return_value=77)
    def test_on_process(self, mocked_time):
        """ Test the reception of a Supervisor PROCESS event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # create a publisher patch
        listener.publisher = Mock(**{'send_process_event.return_value': None})
        # test non-process event
        with self.assertRaises(AttributeError):
            listener.on_process(Tick60Event(0, None))
        # test process event
        process = Mock(pid=1234, spawnerr='resource not available',
                       **{'config.name': 'dummy_process',
                          'config.extra_args': '-s test',
                          'group.config.name': 'dummy_group'})
        event = ProcessStateFatalEvent(process, '')
        listener.on_process(event)
        self.assertEqual([call({'name': 'dummy_process',
                                'group': 'dummy_group',
                                'state': 200,
                                'extra_args': '-s test',
                                'now': 77,
                                'pid': 1234,
                                'expected': True,
                                'spawnerr': 'resource not available'})],
                         listener.publisher.send_process_event.call_args_list)

    @patch.dict('sys.modules',
                **{'supvisors.statscollector': Mock(
                    **{'instant_statistics.return_value': (8.5, [(25, 400)], 76.1, {'lo': (500, 500)}, {})})})
    def test_on_tick(self):
        """ Test the reception of a Supervisor TICK event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # create patches
        listener.publisher = Mock(**{'send_tick_event.return_value': None,
                                     'send_statistics.return_value': None})
        listener.fsm.on_timer_event.return_value = ['10.0.0.1', '10.0.0.4']
        self.supvisors.context.addresses['127.0.0.1'] = Mock(**{'pid_processes.return_value': []})
        # test non-process event
        with self.assertRaises(AttributeError):
            listener.on_tick(ProcessStateFatalEvent(None, ''))
        # test process event
        event = Tick60Event(120, None)
        listener.on_tick(event)
        self.assertEqual([call({'when': 120})],
                         listener.publisher.send_tick_event.call_args_list)
        self.assertEqual([call((8.5, [(25, 400)], 76.1, {'lo': (500, 500)}, {}))],
                         listener.publisher.send_statistics.call_args_list)
        self.assertEqual([call()], listener.fsm.on_timer_event.call_args_list)
        self.assertEqual([call(['10.0.0.1', '10.0.0.4'])],
                         self.supvisors.zmq.pusher.send_isolate_addresses.call_args_list)

    def test_unstack_event(self):
        """ Test the processing of a Supvisors event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # test tick event
        listener.unstack_event('[0, "10.0.0.1", "data"]')
        self.assertEqual([call('10.0.0.1', 'data')],
                         listener.fsm.on_tick_event.call_args_list)
        self.assertFalse(listener.fsm.on_process_event.called)
        self.assertFalse(listener.statistician.push_statistics.called)
        listener.fsm.on_tick_event.reset_mock()
        # test process event
        listener.unstack_event('[1, "10.0.0.2", {"name": "dummy"}]')
        self.assertFalse(listener.fsm.on_tick_event.called)
        self.assertEqual([call('10.0.0.2', {"name": "dummy"})],
                         listener.fsm.on_process_event.call_args_list)
        self.assertFalse(listener.statistician.push_statistics.called)
        listener.fsm.on_process_event.reset_mock()
        # test statistics event
        listener.unstack_event('[2, "10.0.0.3", [0, [[20, 30]], {"lo": [100, 200]}, {}]]')
        self.assertFalse(listener.fsm.on_tick_event.called)
        self.assertFalse(listener.fsm.on_process_event.called)
        self.assertEqual([call('10.0.0.3', [0, [[20, 30]], {"lo": [100, 200]}, {}])],
                         listener.statistician.push_statistics.call_args_list)

    def test_unstack_info(self):
        """ Test the processing of a Supvisors information. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # test info event
        listener.unstack_info('["10.0.0.4", {"name": "dummy"}]')
        self.assertEqual([call('10.0.0.4', {"name": "dummy"})],
                         listener.fsm.on_process_info.call_args_list)

    def test_authorization(self):
        """ Test the processing of a Supvisors authorization. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        listener.authorization('address_name:10.0.0.5 authorized:False master_address:10.0.0.1')
        self.assertEqual([call('10.0.0.5', False, '10.0.0.1')], listener.fsm.on_authorization.call_args_list)

    def test_on_remote_event(self):
        """ Test the reception of a Supervisor remote comm event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # add patches for what is tested just above
        with patch.multiple(listener, unstack_event=DEFAULT,
                            unstack_info=DEFAULT, authorization=DEFAULT):
            # test unknown type
            event = Mock(type='unknown', data='')
            listener.on_remote_event(event)
            listener.unstack_event.assert_not_called()
            listener.unstack_info.assert_not_called()
            listener.authorization.assert_not_called()
            # test event
            event = Mock(type='event', data={'state': 'RUNNING'})
            listener.on_remote_event(event)
            self.assertEqual([call({'state': 'RUNNING'})],
                             listener.unstack_event.call_args_list)
            listener.unstack_info.assert_not_called()
            listener.authorization.assert_not_called()
            listener.unstack_event.reset_mock()
            # test info
            event = Mock(type='info', data={'name': 'dummy_process'})
            listener.on_remote_event(event)
            listener.unstack_event.assert_not_called()
            self.assertEqual([call({'name': 'dummy_process'})],
                             listener.unstack_info.call_args_list)
            listener.authorization.assert_not_called()
            listener.unstack_info.reset_mock()
            # test authorization
            event = Mock(type='auth', data=('10.0.0.1', True))
            listener.on_remote_event(event)
            listener.unstack_event.assert_not_called()
            listener.unstack_info.assert_not_called()
            self.assertEqual([call(('10.0.0.1', True))],
                             listener.authorization.call_args_list)

    @patch('supvisors.listener.time.time', return_value=56)
    def test_force_process_state(self, mocked_time):
        """ Test the sending of a fake Supervisor process event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # patch publisher
        listener.publisher = Mock(**{'send_process_event.return_value': None})
        # test the call
        listener.force_process_state('appli:process', 200)
        self.assertEqual([call({'processname': 'process', 'groupname': 'appli', 'state': 200,
                                'now': 56, 'pid': 0, 'expected': False})],
                         listener.publisher.send_process_event.call_args_list)

    def test_force_process_fatal(self):
        """ Test the sending of a fake FATAL Supervisor process event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # add patch for what is tested just above
        with patch.object(listener, 'force_process_state') as mocked_force:
            listener.force_process_fatal('appli:process')
            self.assertEqual([call('appli:process', 200)], mocked_force.call_args_list)

    def test_force_process_unknown(self):
        """ Test the sending of a fake UNKNOWN Supervisor process event. """
        from supvisors.listener import SupervisorListener
        listener = SupervisorListener(self.supvisors)
        # add patch for what is tested just above
        with patch.object(listener, 'force_process_state') as mocked_force:
            listener.force_process_unknown('appli:process')
            self.assertEqual([call('appli:process', 1000)], mocked_force.call_args_list)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
