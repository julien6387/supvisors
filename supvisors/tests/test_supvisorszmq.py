#!/usr/bin/python
#-*- coding: utf-8 -*-

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

import os
import psutil
import sys
import time
import unittest
import zmq

from supvisors.tests.base import DummySupvisors


def get_connections(port):
    """ Find the network connections related to port. """
    listen = []
    laddr = []
    raddr = []
    for conn in psutil.net_connections():
        if conn.status == 'LISTEN':
            if conn.laddr[1] == port:
                listen.append(conn)
        elif conn.status in ['ESTABLISHED', 'SYN_SENT']:
            if conn.laddr[1] == port:
                laddr.append(conn)
            elif conn.raddr[1] == port:
                raddr.append(conn)
    return listen, laddr, raddr


class ZmqContextTest(unittest.TestCase):
    """ Test case for the create_zmq_context function of the supvisorszmq module. """

    def test_create_context(self):
        """ Create a dummy supvisors and a ZMQ context. """
        from supvisors.supvisorszmq import create_zmq_context
        # create and check context
        zmq_context = create_zmq_context()
        self.assertIsInstance(zmq_context, zmq.Context)
        self.assertFalse(zmq_context.closed)
        self.assertEqual(0, zmq_context.getsockopt(zmq.LINGER))
        # destroy the context
        zmq_context.destroy()
        self.assertTrue(zmq_context.closed)


class ZmqSocketTest(unittest.TestCase):
    """ Test case for the ZeroMQ sockets created in the supvisorszmq module. """

    def setUp(self):
        """ Create a dummy supvisors and a ZMQ context. """
        from supvisors.supvisorszmq import create_zmq_context
        # the dummy Supvisors is used for addresses and ports
        self.supvisors = DummySupvisors()
        # create the ZeroMQ context
        self.zmq_context = create_zmq_context()

    def tearDown(self):
        """ Destroy the ZMQ context. """
        self.zmq_context.destroy(True)

    def test_internal_publish_subscribe(self):
        """ Test the ZeroMQ publish-subscribe sockets used internally in Supvisors. """
        from supvisors.supvisorszmq import InternalEventPublisher, InternalEventSubscriber
        # get internal port
        port = self.supvisors.options.internal_port
        # create publisher and subscriber
        publisher = InternalEventPublisher(self.zmq_context, self.supvisors)
        subscriber = InternalEventSubscriber(self.zmq_context, self.supvisors)
        # check that the ZMQ sockets are ready
        self.assertFalse(publisher.socket.closed)
        self.assertFalse(subscriber.socket.closed)
        # keep pid
        pid = os.getpid()
        # check the TCP connections
        listen, laddr, raddr = get_connections(port)
        # check the listen connection
        self.assertEqual(1, len(listen))
        self.assertEqual(pid, listen[0].pid)
        self.assertEqual('0.0.0.0', listen[0].laddr[0])
        # check the established connection on subscriber side
        self.assertEqual(1, len(laddr))
        self.assertEqual(pid, laddr[0].pid)
        self.assertEqual('ESTABLISHED', laddr[0].status)
        self.assertTupleEqual(('127.0.0.1', port), laddr[0].laddr)
        dyn_port = laddr[0].raddr[1]
        # check the connections on publisher side
        addresses = [conn.raddr[0] for conn in raddr]
        self.assertItemsEqual(self.supvisors.address_mapper.addresses, addresses)
        for conn in raddr:
            self.assertEqual(pid, conn.pid)
            if conn.raddr[0] == '127.0.0.1':
                self.assertEqual('ESTABLISHED', conn.status)
                self.assertEqual(dyn_port, conn.laddr[1])
            else:
                self.assertEqual('SYN_SENT', conn.status)
        # disconnection cannot be tested here
        # ZeroMQ keeps the connection ESTABLISHED for a while
        # however, it can be tested that messages are not received anymore
        # close the sockets
        publisher.close()
        subscriber.close()
        # check that the ZMQ socket are closed
        self.assertTrue(publisher.socket.closed)
        self.assertTrue(subscriber.socket.closed)
        # check that the TCP socket is closed
        listen, laddr, raddr = get_connections(port)
        self.assertFalse(listen)
        self.assertFalse(laddr)
        self.assertFalse(raddr)

    def test_external_publish_subscribe(self):
        """ Test the ZeroMQ publish-subscribe sockets used in the event interface of Supvisors. """
        from supvisors.supvisorszmq import EventPublisher, EventSubscriber
        # get event port
        port = self.supvisors.options.event_port
        # create publisher and subscriber
        publisher = EventPublisher(self.zmq_context, self.supvisors)
        subscriber = EventSubscriber(self.zmq_context, port, self.supvisors.logger)
        # check that the ZMQ sockets are ready
        self.assertFalse(publisher.socket.closed)
        self.assertFalse(subscriber.socket.closed)
        # keep pid
        pid = os.getpid()
        # check the TCP connections
        listen, laddr, raddr = get_connections(port)
        # check the listen connection
        self.assertEqual(1, len(listen))
        self.assertEqual(pid, listen[0].pid)
        self.assertEqual('127.0.0.1', listen[0].laddr[0])
        # check the established connection on subscriber side
        self.assertEqual(1, len(laddr))
        self.assertEqual(pid, laddr[0].pid)
        self.assertEqual('ESTABLISHED', laddr[0].status)
        self.assertTupleEqual(('127.0.0.1', port), laddr[0].laddr)
        dyn_port = laddr[0].raddr[1]
        # check the connections on publisher side
        self.assertEqual(1, len(raddr))
        self.assertEqual(pid, raddr[0].pid)
        self.assertEqual('ESTABLISHED', raddr[0].status)
        self.assertTupleEqual(('127.0.0.1', port), raddr[0].raddr)
        self.assertEqual(dyn_port, raddr[0].laddr[1])
        # close the sockets
        publisher.close()
        subscriber.close()
        # check that the ZMQ socket are closed
        self.assertTrue(publisher.socket.closed)
        self.assertTrue(subscriber.socket.closed)
        # check that the TCP socket is closed
        listen, laddr, raddr = get_connections(port)
        self.assertFalse(listen)
        self.assertFalse(laddr)
        self.assertFalse(raddr)

    def test_internal_pusher_puller(self):
        """ Test the ZeroMQ push-pull sockets used internally in Supvisors. """
        from supvisors.supvisorszmq import RequestPusher, RequestPuller
        from supvisors.utils import IPC_NAME
        # test IPC file absence
        self.assertFalse(os.path.exists(IPC_NAME))
        # create publisher and subscriber
        pusher = RequestPusher(self.zmq_context, self.supvisors)
        puller = RequestPuller(self.zmq_context, self.supvisors)
        # check that the ZMQ sockets are ready
        self.assertFalse(pusher.socket.closed)
        self.assertFalse(puller.socket.closed)
        # test IPC file existence
        self.assertTrue(os.path.exists(IPC_NAME))
        # close the sockets
        pusher.close()
        puller.close()
        # check that the ZMQ socket are closed
        self.assertTrue(pusher.socket.closed)
        self.assertTrue(puller.socket.closed)
        # test IPC file absence after a few seconds
        time.sleep(1)
        self.assertFalse(os.path.exists(IPC_NAME))


class InternalEventTest(unittest.TestCase):
    """ Test case for the InternalEventPublisher and InternalEventSubscriber classes of the supvisorszmq module. """

    def setUp(self):
        """ Create a dummy supvisors, ZMQ context and sockets. """
        from supvisors.supvisorszmq import create_zmq_context, InternalEventPublisher, InternalEventSubscriber
        # the dummy Supvisors is used for addresses and ports
        self.supvisors = DummySupvisors()
        # create the ZeroMQ context
        self.zmq_context = create_zmq_context()
        # create publisher and subscriber
        self.publisher = InternalEventPublisher(self.zmq_context, self.supvisors)
        self.subscriber = InternalEventSubscriber(self.zmq_context, self.supvisors)
        # socket configuration is meant to be blocking
        # however, a failure would block the unit test, so a timeout is set for reception
        self.subscriber.socket.setsockopt(zmq.RCVTIMEO, 1000)
        # publisher does not wait for subscriber clients to work, so give some time for connections
        time.sleep(1)

    def tearDown(self):
        """ Destroy the ZMQ context. """
        # close the ZeroMQ sockets
        self.publisher.close()
        self.subscriber.close()
        # destroy the ZeroMQ context
        self.zmq_context.destroy(True)

    def receive(self, event_type):
        """ This method performs a checked reception on the subscriber. """
        try:
            return self.subscriber.receive()
        except zmq.Again:
            self.fail('Failed to get {} event'. format(event_type))

    def test_disconnection(self):
        """ Test the disconnection of subscribers. """
        from supvisors.utils import InternalEventHeaders
        # get the local address
        local_address = self.supvisors.address_mapper.local_address
        # test remote disconnection
        address = next(address for address in self.supvisors.address_mapper.addresses if address != local_address)
        self.subscriber.disconnect([address])
        # send a tick event from the local publisher
        payload = {'date': 1000}
        self.publisher.send_tick_event(payload)
        # check the reception of the tick event
        msg = self.receive('Tick')
        self.assertTupleEqual((InternalEventHeaders.TICK, local_address, payload), msg)
        # test local disconnection
        self.subscriber.disconnect([local_address])
        # send a tick event from the local publisher
        self.publisher.send_tick_event(payload)
        # check the non-reception of the tick event
        with self.assertRaises(zmq.Again):
            self.subscriber.receive()

    def test_tick_event(self):
        """ Test the publication and subscription of the messages. """
        from supvisors.utils import InternalEventHeaders
        # get the local address
        local_address = self.supvisors.address_mapper.local_address
        # send a tick event
        payload = {'date': 1000}
        self.publisher.send_tick_event(payload)
        # check the reception of the tick event
        msg = self.receive('Tick')
        self.assertTupleEqual((InternalEventHeaders.TICK, local_address, payload), msg)

    def test_process_event(self):
        """ Test the publication and subscription of the process events. """
        from supvisors.utils import InternalEventHeaders
        # get the local address
        local_address = self.supvisors.address_mapper.local_address
        # send a process event
        payload = {'name': 'dummy_program', 'state': 'running'}
        self.publisher.send_process_event(payload)
        # check the reception of the process event
        msg = self.receive('Process')
        self.assertTupleEqual((InternalEventHeaders.PROCESS, local_address, payload), msg)

    def test_statistics(self):
        """ Test the publication and subscription of the statistics messages. """
        from supvisors.utils import InternalEventHeaders
        # get the local address
        local_address = self.supvisors.address_mapper.local_address
        # send a statistics event
        payload = {'cpu': 15, 'mem': 5, 'io': (1234, 4321)}
        self.publisher.send_statistics(payload)
        # check the reception of the statistics event
        msg = self.receive('Statistics')
        self.assertTupleEqual((InternalEventHeaders.STATISTICS, local_address, payload), msg)


class RequestTest(unittest.TestCase):
    """ Test case for the InternalEventPublisher and InternalEventSubscriber classes of the supvisorszmq module. """

    def setUp(self):
        """ Create a dummy supvisors, ZMQ context and sockets. """
        from supvisors.supvisorszmq import create_zmq_context, RequestPusher, RequestPuller
        # the dummy Supvisors is used for addresses and ports
        self.supvisors = DummySupvisors()
        # create the ZeroMQ context
        self.zmq_context = create_zmq_context()
        # create pusher and puller
        self.pusher = RequestPusher(self.zmq_context, self.supvisors)
        self.puller = RequestPuller(self.zmq_context, self.supvisors)
        # socket configuration is meant to be blocking
        # however, a failure would block the unit test, so a timeout is set for reception
        self.puller.socket.setsockopt(zmq.RCVTIMEO, 1000)

    def tearDown(self):
        """ Destroy the ZMQ context. """
        # close the ZeroMQ sockets
        self.pusher.close()
        self.puller.close()
        # destroy the ZeroMQ context
        self.zmq_context.destroy(True)

    def receive(self, event_type):
        """ This method performs a checked reception on the puller. """
        try:
            return self.puller.receive()
        except zmq.Again:
            self.fail('Failed to get {} request'. format(event_type))

    def test_check_address(self):
        """ The method tests that the 'Check Address' request is sent and received correctly. """
        from supvisors.utils import DeferredRequestHeaders
        self.pusher.send_check_address('10.0.0.1')
        request = self.receive('Check Address')
        self.assertTupleEqual((DeferredRequestHeaders.CHECK_ADDRESS, ('10.0.0.1', )), request)

    def test_isolate_addresses(self):
        """ The method tests that the 'Isolate Addresses' request is sent and received correctly. """
        from supvisors.utils import DeferredRequestHeaders
        self.pusher.send_isolate_addresses(['10.0.0.1', '10.0.0.2'])
        request = self.receive('Isolate Addresses')
        self.assertTupleEqual((DeferredRequestHeaders.ISOLATE_ADDRESSES, (['10.0.0.1', '10.0.0.2'])), request)

    def test_start_process(self):
        """ The method tests that the 'Start Process' request is sent and received correctly. """
        from supvisors.utils import DeferredRequestHeaders
        self.pusher.send_start_process('10.0.0.1', 'application:program', ['-extra', 'arguments'])
        request = self.receive('Start Process')
        self.assertTupleEqual((DeferredRequestHeaders.START_PROCESS,
            ('10.0.0.1', 'application:program', ['-extra', 'arguments'])), request)

    def test_stop_process(self):
        """ The method tests that the 'Stop Process' request is sent and received correctly. """
        from supvisors.utils import DeferredRequestHeaders
        self.pusher.send_stop_process('10.0.0.1', 'application:program')
        request = self.receive('Stop Process')
        self.assertTupleEqual((DeferredRequestHeaders.STOP_PROCESS, ('10.0.0.1', 'application:program')), request)

    def test_restart(self):
        """ The method tests that the 'Restart' request is sent and received correctly. """
        from supvisors.utils import DeferredRequestHeaders
        self.pusher.send_restart('10.0.0.1')
        request = self.receive('Restart')
        self.assertTupleEqual((DeferredRequestHeaders.RESTART, ('10.0.0.1', )), request)

    def test_shutdown(self):
        """ The method tests that the 'Shutdown' request is sent and received correctly. """
        from supvisors.utils import DeferredRequestHeaders
        self.pusher.send_shutdown('10.0.0.1')
        request = self.receive('Shutdown')
        self.assertTupleEqual((DeferredRequestHeaders.SHUTDOWN, ('10.0.0.1', )), request)


class Payload:
    """ Dummy class just implementing a serial method. """
    def __init__(self, data):
        self.data = data
    def serial(self):
        return self.data 


class EventTest(unittest.TestCase):
    """ Test case for the EventPublisher and EventSubscriber classes of the supvisorszmq module. """

    def setUp(self):
        """ Create a dummy supvisors and a ZMQ context. """
        from supvisors.supvisorszmq import create_zmq_context, EventPublisher, EventSubscriber
        # the dummy Supvisors is used for addresses and ports
        self.supvisors = DummySupvisors()
        # create the ZeroMQ context
        self.zmq_context = create_zmq_context()
        # create publisher and subscriber
        self.publisher = EventPublisher(self.zmq_context, self.supvisors)
        self.subscriber = EventSubscriber(self.zmq_context, self.supvisors.options.event_port, self.supvisors.logger)
        # WARN: this subscriber does not include a subscription
        # when using a subscription, use a time sleep to give time to PyZMQ to handle it
        # WARN: socket configuration is meant to be blocking
        # however, a failure would block the unit test, so a timeout is set for reception
        self.subscriber.socket.setsockopt(zmq.RCVTIMEO, 1000)
        # create test payloads
        self.supvisors_payload = Payload({'state': 'running', 'version': '1.0'})
        self.address_payload = Payload({'state': 'silent', 'name': 'cliche01', 'date': 1234})
        self.application_payload = Payload({'state': 'starting', 'name': 'supvisors'})
        self.process_payload = Payload({'state': 'running', 'process_name': 'plugin',
            'application_name': 'supvisors', 'date': 1230})

    def tearDown(self):
        """ Destroy the ZMQ context. """
        self.zmq_context.destroy(True)

    def check_reception(self, header=None, data=None):
        """ The method tests that the message is received correctly or not received at all. """
        if header and data:
            # check that subscriber receives the message
            try:
                msg = self.subscriber.receive()
            except zmq.Again:
                self.fail('Failed to get {} status'.format(header))
            self.assertTupleEqual((header, data), msg)
        else:
            # check the non-reception of the Supvisors status
            with self.assertRaises(zmq.Again):
                self.subscriber.receive()

    def check_supvisors_status(self, subscribed):
        """ The method tests the emission and reception of a Supvisors status,
        depending on the subscription status. """
        from supvisors.utils import EventHeaders
        self.publisher.send_supvisors_status(self.supvisors_payload)
        if subscribed:
            self.check_reception(EventHeaders.SUPVISORS, self.supvisors_payload.data)
        else:
            self.check_reception()

    def check_address_status(self, subscribed):
        """ The method tests the emission and reception of an Address status,
        depending on the subscription status. """
        from supvisors.utils import EventHeaders
        self.publisher.send_address_status(self.address_payload)
        if subscribed:
            self.check_reception(EventHeaders.ADDRESS, self.address_payload.data)
        else:
            self.check_reception()

    def check_application_status(self, subscribed):
        """ The method tests the emission and reception of an Application status,
        depending on the subscription status. """
        from supvisors.utils import EventHeaders
        self.publisher.send_application_status(self.application_payload)
        if subscribed:
            self.check_reception(EventHeaders.APPLICATION, self.application_payload.data)
        else:
            self.check_reception()

    def check_process_status(self, subscribed):
        """ The method tests the emission and reception of a Process status,
        depending on the subscription status. """
        from supvisors.utils import EventHeaders
        self.publisher.send_process_status(self.process_payload)
        if subscribed:
            self.check_reception(EventHeaders.PROCESS, self.process_payload.data)
        else:
            self.check_reception()

    def check_subscription(self, supvisors_subscribed, address_subscribed,
            application_subscribed, process_subscribed):
        """ The method tests the emission and reception of all status,
        depending on their subscription status. """
        time.sleep(1)
        self.check_supvisors_status(supvisors_subscribed)
        self.check_address_status(address_subscribed)
        self.check_application_status(application_subscribed)
        self.check_process_status(process_subscribed)

    def test_no_subscription(self):
        """ Test the non-reception of messages when subscription is not set. """
        # at this stage, no subscription has been set so nothing should be received
        self.check_subscription(False, False, False, False)

    def test_subscription_supvisors_status(self):
        """ Test the reception of Supvisors status messages when related subscription is set. """
        # subscribe to Supvisors status only
        self.subscriber.subscribe_supvisors_status()
        self.check_subscription(True, False, False, False)
        # unsubscribe from Supvisors status
        self.subscriber.unsubscribe_supvisors_status()
        self.check_subscription(False, False, False, False)

    def test_subscription_address_status(self):
        """ Test the reception of Address status messages when related subscription is set. """
        # subscribe to Address status only
        self.subscriber.subscribe_address_status()
        self.check_subscription(False, True, False, False)
        # unsubscribe from Address status
        self.subscriber.unsubscribe_address_status()
        self.check_subscription(False, False, False, False)

    def test_subscription_application_status(self):
        """ Test the reception of Application status messages when related subscription is set. """
        # subscribe to Application status only
        self.subscriber.subscribe_application_status()
        self.check_subscription(False, False, True, False)
        # unsubscribe from Application status
        self.subscriber.unsubscribe_application_status()
        self.check_subscription(False, False, False, False)

    def test_subscription_process_status(self):
        """ Test the reception of Process status messages when related subscription is set. """
        # subscribe to Process status only
        self.subscriber.subscribe_process_status()
        self.check_subscription(False, False, False, True)
        # unsubscribe from Process status
        self.subscriber.unsubscribe_process_status()
        self.check_subscription(False, False, False, False)

    def test_subscription_all_status(self):
        """ Test the reception of all status messages when related subscription is set. """
        # subscribe to every status
        self.subscriber.subscribe_all()
        self.check_subscription(True, True, True, True)
        # unsubscribe all
        self.subscriber.unsubscribe_all()
        self.check_subscription(False, False, False, False)

    def test_subscription_multiple_status(self):
        """ Test the reception of multiple status messages when related subscription is set. """
        # subscribe to Application and Process status
        self.subscriber.subscribe_application_status()
        self.subscriber.subscribe_process_status()
        self.check_subscription(False, False, True, True)
        # set subscription to Address and Process Status
        self.subscriber.unsubscribe_application_status()
        self.subscriber.subscribe_address_status()
        self.check_subscription(False, True, False, True)
        # add subscription to Supvisors Status
        self.subscriber.subscribe_supvisors_status()
        self.check_subscription(True, True, False, True)
        # unsubscribe all
        self.subscriber.unsubscribe_supvisors_status()
        self.subscriber.unsubscribe_address_status()
        self.subscriber.unsubscribe_process_status()
        self.check_subscription(False, False, False, False)


class SupvisorsZmqTest(unittest.TestCase):
    """ Test case for the SupvisorsZmq class of the supvisorszmq module. """

    def setUp(self):
        """ Create a dummy supvisors. """
        self.supvisors = DummySupvisors()

    def test_creation_closure(self):
        """ Test the types of the attributes created. """
        from supvisors.supvisorszmq import (SupvisorsZmq, EventPublisher,
            InternalEventSubscriber, InternalEventPublisher, RequestPuller, RequestPusher)
        sockets = SupvisorsZmq(self.supvisors)
        # test all attribute types
        self.assertIsInstance(sockets.zmq_context, zmq.Context)
        self.assertFalse(sockets.zmq_context.closed)
        self.assertIsInstance(sockets.publisher, EventPublisher)
        self.assertFalse(sockets.publisher.socket.closed)
        self.assertIsInstance(sockets.internal_subscriber, InternalEventSubscriber)
        self.assertFalse(sockets.internal_subscriber.socket.closed)
        self.assertIsInstance(sockets.internal_publisher, InternalEventPublisher)
        self.assertFalse(sockets.internal_publisher.socket.closed)
        self.assertIsInstance(sockets.puller, RequestPuller)
        self.assertFalse(sockets.puller.socket.closed)
        self.assertIsInstance(sockets.pusher, RequestPusher)
        self.assertFalse(sockets.pusher.socket.closed)
        # close the instance
        sockets.close()
        self.assertTrue(sockets.zmq_context.closed)
        self.assertTrue(sockets.publisher.socket.closed)
        self.assertTrue(sockets.internal_subscriber.socket.closed)
        self.assertTrue(sockets.internal_publisher.socket.closed)
        self.assertTrue(sockets.puller.socket.closed)
        self.assertTrue(sockets.pusher.socket.closed)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

