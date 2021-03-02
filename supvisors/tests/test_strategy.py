#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import sys
import unittest

from unittest.mock import Mock, call, patch

from supvisors.tests.base import MockedSupvisors, CompatTestCase


class StartingStrategyTest(CompatTestCase):
    """ Test case for the starting strategies of the strategy module. """

    def setUp(self):
        """ Create a Supvisors-like structure and addresses. """
        self.supvisors = MockedSupvisors()
        # add addresses to context
        from supvisors.address import AddressStatus
        from supvisors.ttypes import AddressStates

        def create_status(name, address_state, loading):
            address_status = Mock(spec=AddressStatus,
                                  address_name=name,
                                  state=address_state)
            address_status.loading.return_value = loading
            return address_status

        addresses = self.supvisors.context.addresses
        addresses['10.0.0.0'] = create_status('10.0.0.0', AddressStates.SILENT, 0)
        addresses['10.0.0.1'] = create_status('10.0.0.1', AddressStates.RUNNING, 50)
        addresses['10.0.0.2'] = create_status('10.0.0.2', AddressStates.ISOLATED, 0)
        addresses['10.0.0.3'] = create_status('10.0.0.3', AddressStates.RUNNING, 20)
        addresses['10.0.0.4'] = create_status('10.0.0.4', AddressStates.UNKNOWN, 0)
        addresses['10.0.0.5'] = create_status('10.0.0.5', AddressStates.RUNNING, 80)
        # initialize dummy address mapper with all address names (keep the alphabetic order)
        self.supvisors.address_mapper.addresses = sorted(addresses.keys())
        self.supvisors.address_mapper.local_address = '10.0.0.1'

    def test_is_loading_valid(self):
        """ Test the validity of an address with an additional loading. """
        from supvisors.strategy import AbstractStartingStrategy
        strategy = AbstractStartingStrategy(self.supvisors)
        # test unknown address
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.10', 1))
        # test not RUNNING address
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.0', 1))
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.2', 1))
        self.assertTupleEqual((False, 0), strategy.is_loading_valid('10.0.0.4', 1))
        # test loaded RUNNING address
        self.assertTupleEqual((False, 50), strategy.is_loading_valid('10.0.0.1', 55))
        self.assertTupleEqual((False, 20), strategy.is_loading_valid('10.0.0.3', 85))
        self.assertTupleEqual((False, 80), strategy.is_loading_valid('10.0.0.5', 25))
        # test not loaded RUNNING address
        self.assertTupleEqual((True, 50), strategy.is_loading_valid('10.0.0.1', 45))
        self.assertTupleEqual((True, 20), strategy.is_loading_valid('10.0.0.3', 75))
        self.assertTupleEqual((True, 80), strategy.is_loading_valid('10.0.0.5', 15))

    def test_get_loading_and_validity(self):
        """ Test the determination of the valid addresses with an additional loading. """
        from supvisors.strategy import AbstractStartingStrategy
        strategy = AbstractStartingStrategy(self.supvisors)
        # test valid addresses with different additional loadings
        self.assertDictEqual({'10.0.0.0': (False, 0), '10.0.0.1': (True, 50),
                              '10.0.0.2': (False, 0), '10.0.0.3': (True, 20), '10.0.0.4': (False, 0),
                              '10.0.0.5': (True, 80)},
                             strategy.get_loading_and_validity('*', 15))
        self.assertDictEqual({'10.0.0.0': (False, 0), '10.0.0.1': (True, 50),
                              '10.0.0.2': (False, 0), '10.0.0.3': (True, 20), '10.0.0.4': (False, 0),
                              '10.0.0.5': (False, 80)},
                             strategy.get_loading_and_validity(self.supvisors.context.addresses.keys(), 45))
        self.assertDictEqual({'10.0.0.1': (False, 50), '10.0.0.3': (True, 20), '10.0.0.5': (False, 80)},
                             strategy.get_loading_and_validity(['10.0.0.1', '10.0.0.3', '10.0.0.5'], 75))
        self.assertDictEqual({'10.0.0.1': (False, 50), '10.0.0.3': (False, 20), '10.0.0.5': (False, 80)},
                             strategy.get_loading_and_validity(['10.0.0.1', '10.0.0.3', '10.0.0.5'], 85))

    def test_sort_valid_by_loading(self):
        """ Test the sorting of the validities of the addresses. """
        from supvisors.strategy import AbstractStartingStrategy
        strategy = AbstractStartingStrategy(self.supvisors)
        self.assertListEqual([('10.0.0.3', 20), ('10.0.0.1', 50), ('10.0.0.5', 80)],
                             strategy.sort_valid_by_loading({'10.0.0.0': (False, 0), '10.0.0.1': (True, 50),
                                                             '10.0.0.2': (False, 0), '10.0.0.3': (True, 20),
                                                             '10.0.0.4': (False, 0), '10.0.0.5': (True, 80)}))
        self.assertListEqual([('10.0.0.3', 20)],
                             strategy.sort_valid_by_loading({'10.0.0.1': (False, 50), '10.0.0.3': (True, 20),
                                                             '10.0.0.5': (False, 80)}))
        self.assertListEqual([],
                             strategy.sort_valid_by_loading({'10.0.0.1': (False, 50), '10.0.0.3': (False, 20),
                                                             '10.0.0.5': (False, 80)}))

    def test_config_strategy(self):
        """ Test the choice of an address according to the CONFIG strategy. """
        from supvisors.strategy import ConfigStrategy
        strategy = ConfigStrategy(self.supvisors)
        # test CONFIG strategy with different values
        self.assertEqual('10.0.0.1', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.1', strategy.get_address('*', 45))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 75))
        self.assertIsNone(strategy.get_address('*', 85))

    def test_less_loaded_strategy(self):
        """ Test the choice of an address according to the LESS_LOADED strategy. """
        from supvisors.strategy import LessLoadedStrategy
        strategy = LessLoadedStrategy(self.supvisors)
        # test LESS_LOADED strategy with different values
        self.assertEqual('10.0.0.3', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 45))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 75))
        self.assertIsNone(strategy.get_address('*', 85))

    def test_most_loaded_strategy(self):
        """ Test the choice of an address according to the MOST_LOADED strategy. """
        from supvisors.strategy import MostLoadedStrategy
        strategy = MostLoadedStrategy(self.supvisors)
        # test MOST_LOADED strategy with different values
        self.assertEqual('10.0.0.5', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.1', strategy.get_address('*', 45))
        self.assertEqual('10.0.0.3', strategy.get_address('*', 75))
        self.assertIsNone(strategy.get_address('*', 85))

    def test_local_strategy(self):
        """ Test the choice of an address according to the LOCAL strategy. """
        from supvisors.strategy import LocalStrategy
        strategy = LocalStrategy(self.supvisors)
        # test LOCAL strategy with different values
        self.assertEqual('10.0.0.1', strategy.address_mapper.local_address)
        self.assertEqual('10.0.0.1', strategy.get_address('*', 15))
        self.assertEqual('10.0.0.1', strategy.get_address('*', 45))
        self.assertIsNone(strategy.get_address('*', 75))

    def test_get_address(self):
        """ Test the choice of an address according to a strategy. """
        from supvisors.ttypes import StartingStrategies
        from supvisors.strategy import get_address
        # test CONFIG strategy
        self.assertEqual('10.0.0.1', get_address(self.supvisors, StartingStrategies.CONFIG, '*', 15))
        self.assertEqual('10.0.0.3', get_address(self.supvisors, StartingStrategies.CONFIG, '*', 75))
        self.assertIsNone(get_address(self.supvisors, StartingStrategies.CONFIG, '*', 85))
        # test LESS_LOADED strategy
        self.assertEqual('10.0.0.3', get_address(self.supvisors, StartingStrategies.LESS_LOADED, '*', 15))
        self.assertEqual('10.0.0.3', get_address(self.supvisors, StartingStrategies.LESS_LOADED, '*', 75))
        self.assertIsNone(get_address(self.supvisors, StartingStrategies.LESS_LOADED, '*', 85))
        # test MOST_LOADED strategy
        self.assertEqual('10.0.0.5', get_address(self.supvisors, StartingStrategies.MOST_LOADED, '*', 15))
        self.assertEqual('10.0.0.3', get_address(self.supvisors, StartingStrategies.MOST_LOADED, '*', 75))
        self.assertIsNone(get_address(self.supvisors, StartingStrategies.MOST_LOADED, '*', 85))
        # test LOCAL strategy
        self.assertEqual('10.0.0.1', get_address(self.supvisors, StartingStrategies.LOCAL, '*', 15))
        self.assertIsNone(get_address(self.supvisors, StartingStrategies.LOCAL, '*', 75))


class ConciliationStrategyTest(CompatTestCase):
    """ Test case for the conciliation strategies of the strategy module. """

    def setUp(self):
        """ Create a Supvisors-like structure and conflicting processes. """
        from supvisors.process import ProcessStatus
        self.supvisors = MockedSupvisors()

        # create conflicting processes
        def create_process_status(name, timed_addresses):
            process_status = Mock(spec=ProcessStatus, process_name=name,
                                  addresses=set(timed_addresses.keys()),
                                  infos={address_name: {'uptime': time}
                                         for address_name, time in timed_addresses.items()})
            process_status.namespec.return_value = name
            return process_status

        self.conflicts = [create_process_status('conflict_1', {'10.0.0.1': 5, '10.0.0.2': 10, '10.0.0.3': 15}),
                          create_process_status('conflict_2', {'10.0.0.4': 6, '10.0.0.2': 5, '10.0.0.0': 4})]

    def test_senicide_strategy(self):
        """ Test the strategy that consists in stopping the oldest processes. """
        from supvisors.strategy import SenicideStrategy
        strategy = SenicideStrategy(self.supvisors)
        strategy.conciliate(self.conflicts)
        # check that the oldest processes are requested to stop on the relevant addresses
        self.assertItemsEqual([call('10.0.0.2', 'conflict_1'),
                               call('10.0.0.3', 'conflict_1'),
                               call('10.0.0.4', 'conflict_2'),
                               call('10.0.0.2', 'conflict_2')],
                              self.supvisors.zmq.pusher.send_stop_process.call_args_list)

    def test_infanticide_strategy(self):
        """ Test the strategy that consists in stopping the youngest processes. """
        from supvisors.strategy import InfanticideStrategy
        strategy = InfanticideStrategy(self.supvisors)
        strategy.conciliate(self.conflicts)
        # check that the youngest processes are requested to stop
        # on the relevant addresses
        self.assertItemsEqual([call('10.0.0.1', 'conflict_1'),
                               call('10.0.0.2', 'conflict_1'),
                               call('10.0.0.2', 'conflict_2'),
                               call('10.0.0.0', 'conflict_2')],
                              self.supvisors.zmq.pusher.send_stop_process.call_args_list)

    def test_user_strategy(self):
        """ Test the strategy that consists in doing nothing (trivial). """
        from supvisors.strategy import UserStrategy
        strategy = UserStrategy(self.supvisors)
        strategy.conciliate(self.conflicts)
        # check that processes are NOT requested to stop
        self.assertEqual(0, self.supvisors.stopper.stop_process.call_count)
        self.assertEqual(0, self.supvisors.zmq.pusher.send_stop_process.call_count)

    def test_stop_strategy(self):
        """ Test the strategy that consists in stopping all processes. """
        from supvisors.strategy import StopStrategy
        strategy = StopStrategy(self.supvisors)
        strategy.conciliate(self.conflicts)
        # check that all processes are requested to stop through the Stopper
        self.assertEqual(0, self.supvisors.zmq.pusher.send_stop_process.call_count)
        self.assertEqual([call(self.conflicts[0]), call(self.conflicts[1])],
                         self.supvisors.stopper.stop_process.call_args_list)

    def test_restart_strategy(self):
        """ Test the strategy that consists in stopping all processes and restart a single one. """
        from supvisors.strategy import RestartStrategy
        # get patches
        mocked_add = self.supvisors.failure_handler.add_job
        mocked_trigger = self.supvisors.failure_handler.trigger_jobs
        # call the conciliation
        strategy = RestartStrategy(self.supvisors)
        strategy.conciliate(self.conflicts)
        # check that all processes are NOT requested to stop directly
        self.assertEqual(0, self.supvisors.stopper.stop_process.call_count)
        self.assertEqual(0, self.supvisors.zmq.pusher.send_stop_process.call_count)
        # test failure_handler call
        self.assertEqual([call(1, self.conflicts[0]), call(1, self.conflicts[1])],
                         mocked_add.call_args_list)
        self.assertEqual(1, mocked_trigger.call_count)

    def test_failure_strategy(self):
        """ Test the strategy that consists in stopping all processes and restart a single one. """
        from supvisors.strategy import FailureStrategy
        # get patches
        mocked_add = self.supvisors.failure_handler.add_default_job
        mocked_trigger = self.supvisors.failure_handler.trigger_jobs
        # call the conciliation
        strategy = FailureStrategy(self.supvisors)
        strategy.conciliate(self.conflicts)
        # check that all processes are requested to stop through the Stopper
        self.assertEqual(0, self.supvisors.zmq.pusher.send_stop_process.call_count)
        self.assertEqual([call(self.conflicts[0]), call(self.conflicts[1])],
                         self.supvisors.stopper.stop_process.call_args_list)
        # test failure_handler call
        self.assertEqual([call(self.conflicts[0]), call(self.conflicts[1])],
                         mocked_add.call_args_list)
        self.assertEqual(1, mocked_trigger.call_count)

    @patch('supvisors.strategy.SenicideStrategy.conciliate')
    @patch('supvisors.strategy.InfanticideStrategy.conciliate')
    @patch('supvisors.strategy.UserStrategy.conciliate')
    @patch('supvisors.strategy.StopStrategy.conciliate')
    @patch('supvisors.strategy.RestartStrategy.conciliate')
    @patch('supvisors.strategy.FailureStrategy.conciliate')
    def test_conciliate_conflicts(self, mocked_failure, mocked_restart, mocked_stop,
                                  mocked_user, mocked_infanticide, mocked_senicide):
        """ Test the actions on process according to a strategy. """
        from supvisors.ttypes import ConciliationStrategies
        from supvisors.strategy import conciliate_conflicts
        # test senicide conciliation
        conciliate_conflicts(self.supvisors, ConciliationStrategies.SENICIDE, self.conflicts)
        self.assertEqual([call(self.conflicts)], mocked_senicide.call_args_list)
        self.assertEqual(0, mocked_infanticide.call_count)
        self.assertEqual(0, mocked_user.call_count)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_restart.call_count)
        self.assertEqual(0, mocked_failure.call_count)
        mocked_senicide.reset_mock()
        # test infanticide conciliation
        conciliate_conflicts(self.supvisors, ConciliationStrategies.INFANTICIDE, self.conflicts)
        self.assertEqual(0, mocked_senicide.call_count)
        self.assertEqual([call(self.conflicts)], mocked_infanticide.call_args_list)
        self.assertEqual(0, mocked_user.call_count)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_restart.call_count)
        self.assertEqual(0, mocked_failure.call_count)
        mocked_infanticide.reset_mock()
        # test user conciliation
        conciliate_conflicts(self.supvisors, ConciliationStrategies.USER, self.conflicts)
        self.assertEqual(0, mocked_senicide.call_count)
        self.assertEqual(0, mocked_infanticide.call_count)
        self.assertEqual([call(self.conflicts)], mocked_user.call_args_list)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_restart.call_count)
        self.assertEqual(0, mocked_failure.call_count)
        mocked_user.reset_mock()
        # test stop conciliation
        conciliate_conflicts(self.supvisors, ConciliationStrategies.STOP, self.conflicts)
        self.assertEqual(0, mocked_senicide.call_count)
        self.assertEqual(0, mocked_infanticide.call_count)
        self.assertEqual(0, mocked_user.call_count)
        self.assertEqual([call(self.conflicts)], mocked_stop.call_args_list)
        self.assertEqual(0, mocked_restart.call_count)
        self.assertEqual(0, mocked_failure.call_count)
        mocked_stop.reset_mock()
        # test restart conciliation
        conciliate_conflicts(self.supvisors, ConciliationStrategies.RESTART, self.conflicts)
        self.assertEqual(0, mocked_senicide.call_count)
        self.assertEqual(0, mocked_infanticide.call_count)
        self.assertEqual(0, mocked_user.call_count)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual([call(self.conflicts)], mocked_restart.call_args_list)
        self.assertEqual(0, mocked_failure.call_count)
        mocked_restart.reset_mock()
        # test restart conciliation
        conciliate_conflicts(self.supvisors, ConciliationStrategies.RUNNING_FAILURE, self.conflicts)
        self.assertEqual(0, mocked_senicide.call_count)
        self.assertEqual(0, mocked_infanticide.call_count)
        self.assertEqual(0, mocked_user.call_count)
        self.assertEqual(0, mocked_stop.call_count)
        self.assertEqual(0, mocked_restart.call_count)
        self.assertEqual([call(self.conflicts)], mocked_failure.call_args_list)


class RunningFailureHandlerTest(CompatTestCase):
    """ Test case for the running failure strategies of the strategy module. """

    def setUp(self):
        """ Create a Supvisors-like structure. """
        self.supvisors = MockedSupvisors()

    def test_create(self):
        """ Test the values set at construction. """
        from supvisors.strategy import RunningFailureHandler
        handler = RunningFailureHandler(self.supvisors)
        # test empty structures
        self.assertEqual(set(), handler.stop_application_jobs)
        self.assertEqual(set(), handler.restart_application_jobs)
        self.assertEqual(set(), handler.restart_process_jobs)
        self.assertEqual(set(), handler.continue_process_jobs)
        self.assertEqual(set(), handler.start_application_jobs)
        self.assertEqual(set(), handler.start_process_jobs)

    def test_clear_jobs(self):
        """ Test the clearance of internal structures. """
        from supvisors.strategy import RunningFailureHandler
        handler = RunningFailureHandler(self.supvisors)
        # add data to sets
        self.stop_application_jobs = {1, 2}
        self.restart_application_jobs = {'a', 'b'}
        self.restart_process_jobs = {1, 0, 'bcd'}
        self.continue_process_jobs = {'aka', 2}
        self.start_application_jobs = {1, None}
        self.start_process_jobs = {0}
        # clear all
        handler.clear_jobs()
        # test empty structures
        self.assertEqual(set(), handler.stop_application_jobs)
        self.assertEqual(set(), handler.restart_application_jobs)
        self.assertEqual(set(), handler.restart_process_jobs)
        self.assertEqual(set(), handler.continue_process_jobs)
        self.assertEqual(set(), handler.start_application_jobs)
        self.assertEqual(set(), handler.start_process_jobs)

    def test_add_job(self):
        """ Test the addition of a new job using a strategy. """
        from supvisors.strategy import RunningFailureHandler
        from supvisors.ttypes import RunningFailureStrategies
        handler = RunningFailureHandler(self.supvisors)
        # create a dummy process
        process_1 = Mock(application_name='dummy_application_A')
        process_2 = Mock(application_name='dummy_application_A')
        process_3 = Mock(application_name='dummy_application_B')

        # define compare function
        def compare_sets(stop_app=set(), restart_app=set(), restart_proc=set(),
                         continue_proc=set(), start_app=set(), start_proc=set()):
            self.assertSetEqual(stop_app, handler.stop_application_jobs)
            self.assertSetEqual(restart_app, handler.restart_application_jobs)
            self.assertSetEqual(restart_proc, handler.restart_process_jobs)
            self.assertSetEqual(continue_proc, handler.continue_process_jobs)
            self.assertSetEqual(start_app, handler.start_application_jobs)
            self.assertSetEqual(start_proc, handler.start_process_jobs)

        # add a series of jobs
        handler.add_job(RunningFailureStrategies.CONTINUE, process_1)
        compare_sets(continue_proc={process_1})
        handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_2)
        compare_sets(restart_proc={process_2}, continue_proc={process_1})
        handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_1)
        compare_sets(restart_proc={process_2, process_1})
        handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_3)
        compare_sets(restart_proc={process_2, process_1, process_3})
        handler.add_job(RunningFailureStrategies.RESTART_PROCESS, process_3)
        compare_sets(restart_proc={process_2, process_1, process_3})
        handler.add_job(RunningFailureStrategies.RESTART_APPLICATION, process_1)
        compare_sets(restart_app={'dummy_application_A'}, restart_proc={process_3})
        handler.add_job(RunningFailureStrategies.STOP_APPLICATION, process_2)
        compare_sets(stop_app={'dummy_application_A'}, restart_proc={process_3})
        handler.add_job(RunningFailureStrategies.RESTART_APPLICATION, process_2)
        compare_sets(stop_app={'dummy_application_A'}, restart_proc={process_3})
        handler.add_job(RunningFailureStrategies.STOP_APPLICATION, process_1)
        compare_sets(stop_app={'dummy_application_A'}, restart_proc={process_3})

    def test_add_default_job(self):
        """ Test the addition of a new job using the strategy configured. """
        from supvisors.strategy import RunningFailureHandler
        handler = RunningFailureHandler(self.supvisors)
        # create a dummy process
        process = Mock()
        process.rules = Mock(running_failure_strategy=2)
        # add a series of jobs
        with patch.object(handler, 'add_job') as mocked_add:
            handler.add_default_job(process)
            self.assertEqual([call(2, process)], mocked_add.call_args_list)

    def test_trigger_jobs(self):
        """ Test the processing of jobs. """
        from supvisors.strategy import RunningFailureHandler
        handler = RunningFailureHandler(self.supvisors)

        # create mocked applications
        def mocked_application(appli_name, stopped):
            application = Mock(aplication_name=appli_name,
                               **{'stopped.side_effect': [stopped, True]})
            self.supvisors.context.applications[appli_name] = application
            return application

        stop_appli_A = mocked_application('stop_application_A', False)
        stop_appli_B = mocked_application('stop_application_B', False)
        restart_appli_A = mocked_application('restart_application_A', False)
        restart_appli_B = mocked_application('restart_application_B', False)
        start_appli_A = mocked_application('start_application_A', True)
        start_appli_B = mocked_application('start_application_B', True)

        # create mocked processes
        def mocked_process(namespec, stopped):
            return Mock(**{'namespec.return_value': namespec,
                           'stopped.side_effect': [stopped, True]})

        restart_process_1 = mocked_process('restart_process_1', False)
        restart_process_2 = mocked_process('restart_process_2', False)
        start_process_1 = mocked_process('start_process_1', True)
        start_process_2 = mocked_process('start_process_2', True)
        continue_process = mocked_process('continue_process', False)

        # pre-fill sets
        handler.stop_application_jobs = {'stop_application_A', 'stop_application_B'}
        handler.restart_application_jobs = {'restart_application_A', 'restart_application_B'}
        handler.restart_process_jobs = {restart_process_1, restart_process_2}
        handler.continue_process_jobs = {continue_process}
        handler.start_application_jobs = {start_appli_A, start_appli_B}
        handler.start_process_jobs = {start_process_1, start_process_2}
        # get patches to starter and stopper
        mocked_stop_app = self.supvisors.stopper.stop_application
        mocked_start_app = self.supvisors.starter.default_start_application
        mocked_stop_proc = self.supvisors.stopper.stop_process
        mocked_start_proc = self.supvisors.starter.default_start_process
        # test jobs trigger
        handler.trigger_jobs()
        # check called patches
        self.assertItemsEqual([call(stop_appli_A), call(stop_appli_B),
                               call(restart_appli_A), call(restart_appli_B)],
                              mocked_stop_app.call_args_list)
        # test start application calls
        self.assertItemsEqual([call(start_appli_A), call(start_appli_B)],
                              mocked_start_app.call_args_list)
        # test stop process calls
        self.assertItemsEqual([call(restart_process_1), call(restart_process_2)],
                              mocked_stop_proc.call_args_list)
        # test start process calls
        self.assertItemsEqual([call(start_process_1), call(start_process_2)],
                              mocked_start_proc.call_args_list)
        # check impact on sets
        self.assertSetEqual(set(), handler.stop_application_jobs)
        self.assertSetEqual(set(), handler.restart_application_jobs)
        self.assertSetEqual(set(), handler.restart_process_jobs)
        self.assertSetEqual(set(), handler.continue_process_jobs)
        self.assertSetEqual({restart_appli_A, restart_appli_B}, handler.start_application_jobs)
        self.assertSetEqual({restart_process_1, restart_process_2}, handler.start_process_jobs)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
