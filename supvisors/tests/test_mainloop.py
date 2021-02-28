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
from threading import Thread

from supvisors.tests.base import MockedSupvisors, DummyRpcInterface


class MainLoopTest(unittest.TestCase):
    """ Test case for the mainloop module. """

    def setUp(self):
        """ Create a Supvisors-like structure and patch getRPCInterface. """
        self.supvisors = MockedSupvisors()
        self.rpc_patch = patch('supvisors.mainloop.getRPCInterface')
        self.mocked_rpc = self.rpc_patch.start()

    def tearDown(self):
        """ Remove patch of getRPCInterface. """
        self.rpc_patch.stop()

    def test_creation(self):
        """ Test the values set at construction. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        self.assertIsInstance(main_loop, Thread)
        self.assertIs(self.supvisors, main_loop.supvisors)
        self.assertFalse(main_loop.stop_event.is_set())
        self.assertDictEqual({'SUPERVISOR_SERVER_URL': 'http://127.0.0.1:65000',
                              'SUPERVISOR_USERNAME': '',
                              'SUPERVISOR_PASSWORD': ''},
                             main_loop.env)
        self.assertEqual(1, self.mocked_rpc.call_count)
        self.assertEqual(call('localhost', main_loop.env),
                         self.mocked_rpc.call_args)

    def test_stopping(self):
        """ Test the get_loop method. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        self.assertFalse(main_loop.stopping())
        main_loop.stop_event.set()
        self.assertTrue(main_loop.stopping())

    def test_stop(self):
        """ Test the stopping of the main loop thread. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        with patch.object(main_loop, 'join') as mocked_join:
            # try to stop main loop before it is started
            main_loop.stop()
            self.assertFalse(main_loop.stop_event.is_set())
            self.assertEqual(0, mocked_join.call_count)
            # stop main loop when alive
            with patch.object(main_loop, 'is_alive', return_value=True):
                main_loop.stop()
                self.assertTrue(main_loop.stop_event.is_set())
                self.assertEqual(1, mocked_join.call_count)

    @patch('supvisors.mainloop.SupvisorsMainLoop.check_events')
    @patch('supvisors.mainloop.SupvisorsMainLoop.check_requests')
    @patch.multiple('supvisors.mainloop.zmq.Poller', register=DEFAULT,
                    unregister=DEFAULT, poll=DEFAULT)
    def test_run(self, check_evt, check_rqt, register, unregister, poll):
        """ Test the running of the main loop thread. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # patch one loops
        with patch.object(main_loop, 'stopping',
                          side_effect=[False, False, True]):
            main_loop.run()
        # test that register was called twice
        self.assertEqual(2, register.call_count)
        # test that poll was called once
        self.assertEqual([call(500)], poll.call_args_list)
        # test that check_events was called once
        self.assertEqual(1, check_evt.call_count)
        # test that check_requests was called once
        self.assertEqual(1, check_rqt.call_count)
        # test that unregister was called twice
        self.assertEqual(2, unregister.call_count)

    @patch('supvisors.mainloop.stderr')
    @patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    def test_check_events(self, mocked_send, mocked_stderr):
        """ Test the processing of the events received. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test with empty socks
        mocked_subscriber = Mock(socket='zmq socket')
        socks = {}
        main_loop.check_events(mocked_subscriber, socks)
        self.assertEqual(0, mocked_subscriber.call_count)
        self.assertEqual(0, mocked_send.call_count)
        # test with appropriate socks but with exception
        mocked_subscriber = Mock(
            socket='zmq socket', **{'receive.side_effect': Exception})
        socks = {'zmq socket': 1}
        main_loop.check_events(mocked_subscriber, socks)
        self.assertEqual(1, mocked_subscriber.receive.call_count)
        self.assertEqual(0, mocked_send.call_count)
        mocked_subscriber.receive.reset_mock()
        # test with appropriate socks and without exception
        mocked_subscriber = Mock(
            socket='zmq socket', **{'receive.return_value': 'a zmq message'})
        main_loop.check_events(mocked_subscriber, socks)
        self.assertEqual(1, mocked_subscriber.receive.call_count)
        self.assertEqual([call('event', '"a zmq message"')],
                         mocked_send.call_args_list)

    @patch('supvisors.mainloop.stderr')
    @patch('supvisors.mainloop.SupvisorsMainLoop.send_request')
    def test_check_requests(self, mocked_send, mocked_stderr):
        """ Test the processing of the requests received. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # mock parameters
        mocked_sockets = Mock(
            puller=Mock(socket='zmq socket',
                        **{'receive.side_effect': Exception}),
            internal_subscriber=Mock(**{'disconnect.return_value': None}))
        mocked_receive = mocked_sockets.puller.receive
        mocked_disconnect = mocked_sockets.internal_subscriber.disconnect
        # test with empty socks
        socks = {}
        main_loop.check_requests(mocked_sockets, socks)
        self.assertEqual(0, mocked_receive.call_count)
        self.assertEqual(0, mocked_send.call_count)
        self.assertEqual(0, mocked_disconnect.call_count)
        # test with appropriate socks but with exception
        socks = {'zmq socket': 1}
        main_loop.check_requests(mocked_sockets, socks)
        self.assertEqual(1, mocked_receive.call_count)
        self.assertEqual(0, mocked_send.call_count)
        self.assertEqual(0, mocked_disconnect.call_count)
        mocked_receive.reset_mock()
        # test with appropriate socks and without exception
        mocked_receive.side_effect = None
        mocked_receive.return_value = ('a zmq header', 'a zmq message')
        main_loop.check_requests(mocked_sockets, socks)
        self.assertEqual([call('a zmq header', 'a zmq message')],
                         mocked_send.call_args_list)
        self.assertEqual(0, mocked_disconnect.call_count)
        mocked_receive.reset_mock()
        mocked_send.reset_mock()
        # test disconnection request
        mocked_receive.return_value = (1, 'an address')
        main_loop.check_requests(mocked_sockets, socks)
        self.assertEqual(1, mocked_receive.call_count)
        self.assertEqual([call('an address')],
                         mocked_disconnect.call_args_list)
        self.assertEqual(0, mocked_send.call_count)

    @patch('supvisors.mainloop.stderr')
    @patch('supvisors.mainloop.SupvisorsMainLoop.send_remote_comm_event')
    def test_check_address(self, mocked_evt: Mock, mocked_stderr: Mock):
        """ Test the protocol to get the processes handled by a remote Supervisor. """
        from supvisors.mainloop import SupvisorsMainLoop
        from supvisors.ttypes import AddressStates
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test rpc error: no event is sent to local Supervisor
        self.mocked_rpc.side_effect = Exception
        main_loop.check_address('10.0.0.1')
        self.assertEqual(2, self.mocked_rpc.call_count)
        self.assertEqual(call('10.0.0.1', main_loop.env), self.mocked_rpc.call_args)
        self.assertEqual(0, mocked_evt.call_count)
        # test with a mocked rpc interface
        dummy_info = [{'name': 'proc', 'group': 'appli', 'state': 10, 'start': 5,
                       'now': 10, 'pid': 1234, 'spawnerr': ''}]
        rpc_intf = DummyRpcInterface()
        mocked_all = rpc_intf.supervisor.getAllProcessInfo = Mock()
        mocked_local = rpc_intf.supvisors.get_all_local_process_info = Mock(return_value=dummy_info)
        mocked_addr = rpc_intf.supvisors.get_address_info = Mock()
        rpc_intf.supvisors.get_master_address = Mock(return_value='10.0.0.5')
        self.mocked_rpc.return_value = rpc_intf
        self.mocked_rpc.side_effect = None
        self.mocked_rpc.reset_mock()
        # test with address in isolation
        for state in [AddressStates.ISOLATING, AddressStates.ISOLATED]:
            mocked_addr.return_value = {'statecode': state}
            main_loop.check_address('10.0.0.1')
            self.assertEqual([call('10.0.0.1', main_loop.env)], self.mocked_rpc.call_args_list)
            self.assertEqual([call('auth', 'address_name:10.0.0.1 authorized:False master_address:10.0.0.5')],
                             mocked_evt.call_args_list)
            self.assertFalse(mocked_all.called)
            # reset counters
            mocked_evt.reset_mock()
            self.mocked_rpc.reset_mock()
        # test with address not in isolation
        for state in [AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.RUNNING, AddressStates.SILENT]:
            mocked_addr.return_value = {'statecode': state}
            main_loop.check_address('10.0.0.1')
            self.assertEqual(1, self.mocked_rpc.call_count)
            self.assertEqual(call('10.0.0.1', main_loop.env), self.mocked_rpc.call_args)
            self.assertEqual(2, mocked_evt.call_count)
            self.assertEqual(1, mocked_local.call_count)
            # reset counters
            mocked_evt.reset_mock()
            mocked_local.reset_mock()
            self.mocked_rpc.reset_mock()

    @patch('supvisors.mainloop.stderr')
    def test_start_process(self, mocked_stderr):
        """ Test the protocol to start a process handled by a remote
        Supervisor. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test rpc error
        self.mocked_rpc.side_effect = Exception
        main_loop.start_process('10.0.0.1', 'dummy_process', 'extra args')
        self.assertEqual(2, self.mocked_rpc.call_count)
        self.assertEqual(call('10.0.0.1', main_loop.env),
                         self.mocked_rpc.call_args)
        # test with a mocked rpc interface
        rpc_intf = DummyRpcInterface()
        self.mocked_rpc.side_effect = None
        self.mocked_rpc.return_value = rpc_intf
        with patch.object(rpc_intf.supvisors,
                          'start_args') as mocked_supvisors:
            main_loop.start_process('10.0.0.1', 'dummy_process', 'extra args')
            self.assertEqual(3, self.mocked_rpc.call_count)
            self.assertEqual(call('10.0.0.1', main_loop.env),
                             self.mocked_rpc.call_args)
            self.assertEqual(1, mocked_supvisors.call_count)
            self.assertEqual(call('dummy_process', 'extra args', False),
                             mocked_supvisors.call_args)

    @patch('supvisors.mainloop.stderr')
    def test_stop_process(self, mocked_stderr):
        """ Test the protocol to stop a process handled by a remote
        Supervisor. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test rpc error
        self.mocked_rpc.side_effect = Exception
        main_loop.stop_process('10.0.0.1', 'dummy_process')
        self.assertEqual(2, self.mocked_rpc.call_count)
        self.assertEqual(call('10.0.0.1', main_loop.env),
                         self.mocked_rpc.call_args)
        # test with a mocked rpc interface
        rpc_intf = DummyRpcInterface()
        self.mocked_rpc.side_effect = None
        self.mocked_rpc.return_value = rpc_intf
        with patch.object(rpc_intf.supervisor,
                          'stopProcess') as mocked_supervisor:
            main_loop.stop_process('10.0.0.1', 'dummy_process')
            self.assertEqual(3, self.mocked_rpc.call_count)
            self.assertEqual(call('10.0.0.1', main_loop.env),
                             self.mocked_rpc.call_args)
            self.assertEqual(1, mocked_supervisor.call_count)
            self.assertEqual(call('dummy_process', False),
                             mocked_supervisor.call_args)

    @patch('supvisors.mainloop.stderr')
    def test_restart(self, mocked_stderr):
        """ Test the protocol to restart a remote Supervisor. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test rpc error
        self.mocked_rpc.side_effect = Exception
        main_loop.restart('10.0.0.1')
        self.assertEqual(2, self.mocked_rpc.call_count)
        self.assertEqual(call('10.0.0.1', main_loop.env),
                         self.mocked_rpc.call_args)
        # test with a mocked rpc interface
        rpc_intf = DummyRpcInterface()
        self.mocked_rpc.side_effect = None
        self.mocked_rpc.return_value = rpc_intf
        with patch.object(rpc_intf.supervisor,
                          'restart') as mocked_supervisor:
            main_loop.restart('10.0.0.1')
            self.assertEqual(3, self.mocked_rpc.call_count)
            self.assertEqual(call('10.0.0.1', main_loop.env),
                             self.mocked_rpc.call_args)
            self.assertEqual(1, mocked_supervisor.call_count)
            self.assertEqual(call(), mocked_supervisor.call_args)

    @patch('supvisors.mainloop.stderr')
    def test_shutdown(self, mocked_stderr):
        """ Test the protocol to shutdown a remote Supervisor. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test rpc error
        self.mocked_rpc.side_effect = Exception
        main_loop.shutdown('10.0.0.1')
        self.assertEqual(2, self.mocked_rpc.call_count)
        self.assertEqual(call('10.0.0.1', main_loop.env),
                         self.mocked_rpc.call_args)
        # test with a mocked rpc interface
        rpc_intf = DummyRpcInterface()
        self.mocked_rpc.side_effect = None
        self.mocked_rpc.return_value = rpc_intf
        with patch.object(rpc_intf.supervisor, 'shutdown') as mocked_shutdown:
            main_loop.shutdown('10.0.0.1')
            self.assertEqual(3, self.mocked_rpc.call_count)
            self.assertEqual(call('10.0.0.1', main_loop.env),
                             self.mocked_rpc.call_args)
            self.assertEqual(1, mocked_shutdown.call_count)
            self.assertEqual(call(), mocked_shutdown.call_args)

    @patch('supvisors.mainloop.stderr')
    def test_comm_event(self, mocked_stderr):
        """ Test the protocol to send a comm event to the local Supervisor. """
        from supvisors.mainloop import SupvisorsMainLoop
        main_loop = SupvisorsMainLoop(self.supvisors)
        # test rpc error
        with patch.object(main_loop.proxy.supervisor, 'sendRemoteCommEvent',
                          side_effect=Exception):
            main_loop.send_remote_comm_event('event type', 'event data')
        # test with a mocked rpc interface
        with patch.object(main_loop.proxy.supervisor,
                          'sendRemoteCommEvent') as mocked_supervisor:
            main_loop.send_remote_comm_event('event type', 'event data')
            self.assertEqual(1, mocked_supervisor.call_count)
            self.assertEqual(call('event type', 'event data'),
                             mocked_supervisor.call_args)

    def check_call(self, main_loop, mocked_loop,
                   method_name, request, args):
        """ Perform a main loop request and check what has been called. """
        # send request
        main_loop.send_request(request, args)
        # test mocked main loop
        for key, mocked in mocked_loop.items():
            if key == method_name:
                self.assertEqual(1, mocked.call_count)
                self.assertEqual(call(*args), mocked.call_args)
                mocked.reset_mock()
            else:
                self.assertEqual(0, mocked.call_count)

    def test_send_request(self):
        """ Test the execution of a deferred Supervisor request. """
        from supvisors.mainloop import SupvisorsMainLoop
        from supvisors.utils import DeferredRequestHeaders
        main_loop = SupvisorsMainLoop(self.supvisors)
        # patch main loop subscriber
        with patch.multiple(main_loop, check_address=DEFAULT,
                            start_process=DEFAULT, stop_process=DEFAULT,
                            restart=DEFAULT, shutdown=DEFAULT) as mocked_loop:
            # test check address
            self.check_call(main_loop, mocked_loop, 'check_address',
                            DeferredRequestHeaders.CHECK_ADDRESS,
                            ('10.0.0.2',))
            # test start process
            self.check_call(main_loop, mocked_loop, 'start_process',
                            DeferredRequestHeaders.START_PROCESS,
                            ('10.0.0.2', 'dummy_process', 'extra args'))
            # test stop process
            self.check_call(main_loop, mocked_loop, 'stop_process',
                            DeferredRequestHeaders.STOP_PROCESS,
                            ('10.0.0.2', 'dummy_process'))
            # test restart
            self.check_call(main_loop, mocked_loop, 'restart',
                            DeferredRequestHeaders.RESTART,
                            ('10.0.0.2',))
            # test shutdown
            self.check_call(main_loop, mocked_loop, 'shutdown',
                            DeferredRequestHeaders.SHUTDOWN,
                            ('10.0.0.2',))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
