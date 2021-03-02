#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import re
import sys
import unittest

from unittest.mock import call, patch, Mock

from supvisors.tests.base import (DummyAddressMapper,
                                  DummyHttpContext,
                                  DummyOptions)


class ViewContextTest(unittest.TestCase):
    """ Test case for the viewcontext module. """

    url_attr_template = r'(.+=.+)'

    def setUp(self):
        """ Create the instance to be tested. """
        from supvisors.viewcontext import ViewContext
        self.http_context = DummyHttpContext('')
        self.ctx = ViewContext(self.http_context)
        self.maxDiff = None

    def test_init(self):
        """ Test the values set at construction. """
        self.assertIs(self.ctx.http_context, self.http_context)
        self.assertIs(self.ctx.supvisors, self.http_context.supervisord.supvisors)
        self.assertEqual(DummyAddressMapper().local_address, self.ctx.local_address)
        self.assertDictEqual({'address': '10.0.0.4', 'namespec': None, 'period': 5,
                              'appliname': None, 'processname': None, 'cpuid': 0,
                              'intfname': None, 'auto': False, 'strategy': 'CONFIG'},
                             self.ctx.parameters)

    def test_get_server_port(self):
        """ Test the get_server_port method. """
        self.assertEqual(7777, self.ctx.get_server_port())

    def test_get_action(self):
        """ Test the get_action method. """
        self.assertEqual('test', self.ctx.get_action())

    def test_get_address(self):
        """ Test the get_address method. """
        self.assertEqual('10.0.0.4', self.ctx.get_address())

    def test_get_message(self):
        """ Test the get_message method. """
        self.assertEqual('hi chaps', self.ctx.get_message())

    def test_get_gravity(self):
        """ Test the get_gravity method. """
        self.assertEqual('none', self.ctx.get_gravity())

    def test_url_parameters(self):
        """ Test the get_nb_cores method. """
        # test default
        self.assertEqual(self.ctx.url_parameters(), 'period=5')
        # update internal parameters
        self.ctx.parameters.update({'processname': 'dummy_proc',
                                    'namespec': 'dummy_ns',
                                    'address': '10.0.0.1',
                                    'cpuid': 3,
                                    'intfname': 'eth0',
                                    'appliname': 'dummy_appli',
                                    'period': 8})
        # test default
        self.assertEqual(self.ctx.url_parameters(),
                         'processname=dummy_proc&amp;namespec=dummy_ns&amp;'
                         'address=10.0.0.1&amp;cpuid=3&amp;intfname=eth0&amp;'
                         'appliname=dummy_appli&amp;period=8')
        # test with extra arguments, overloading some
        self.assertEqual(self.ctx.url_parameters(**{'extra': 'args',
                                                    'processname': 'cat',
                                                    'address': '127.0.0.1',
                                                    'cpuid': 1,
                                                    'intfname': 'lo',
                                                    'appliname': '',
                                                    'period': 0}),
                         'namespec=dummy_ns&amp;extra=args&amp;'
                         'processname=cat&amp;address=127.0.0.1&amp;'
                         'cpuid=1&amp;intfname=lo')

    def test_cpu_id_to_string(self):
        """ Test the cpu_id_to_string method. """
        from supvisors.viewcontext import ViewContext
        for idx in range(1, 10):
            self.assertEqual(str(idx - 1), ViewContext.cpu_id_to_string(idx))
        self.assertEqual('all', ViewContext.cpu_id_to_string(0))
        self.assertEqual('all', ViewContext.cpu_id_to_string(-5))

    def test_update_string(self):
        """ Test the _update_string method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # keep a copy of parameters
        ref_parameters = ctx.parameters.copy()
        # test with unknown parameter and no default value
        self.assertNotIn('dummy', self.http_context.form)
        ctx._update_string('dummy', [])
        ref_parameters.update({'dummy': None})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with unknown parameter and default value
        self.assertNotIn('dummy', self.http_context.form)
        ctx._update_string('dummy', [], 'hello')
        ref_parameters.update({'dummy': 'hello'})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, no default value and value out of list
        self.assertIn('action', self.http_context.form)
        ctx._update_string('action', [])
        ref_parameters.update({'action': None})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, default value and value out of list
        self.assertIn('action', self.http_context.form)
        ctx._update_string('action', [], 'do it')
        ref_parameters.update({'action': 'do it'})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter and value in list
        self.assertIn('action', self.http_context.form)
        ctx._update_string('action', ['try', 'do it', 'test'])
        ref_parameters.update({'action': 'test'})
        self.assertDictEqual(ref_parameters, ctx.parameters)

    def test_update_integer(self):
        """ Test the _update_integer method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # keep a copy of parameters
        ref_parameters = ctx.parameters.copy()
        # test with unknown parameter and no default value
        self.assertNotIn('dummy', self.http_context.form)
        ctx._update_integer('dummy', [])
        ref_parameters.update({'dummy': 0})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with unknown parameter and default value
        self.assertNotIn('dummy', self.http_context.form)
        ctx._update_integer('dummy', [], 'hello')
        ref_parameters.update({'dummy': 'hello'})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, not integer and no default value
        self.assertIn('action', self.http_context.form)
        ctx._update_integer('action', [])
        ref_parameters.update({'action': 0})
        # test with known parameter, not integer and default value
        self.assertIn('action', self.http_context.form)
        ctx._update_integer('action', [], 5)
        ref_parameters.update({'action': 5})
        # test with known parameter, integer, no default value
        # and value out of list
        self.assertIn('SERVER_PORT', self.http_context.form)
        ctx._update_integer('SERVER_PORT', [])
        ref_parameters.update({'SERVER_PORT': 0})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, integer, default value
        # and value out of list
        self.assertIn('SERVER_PORT', self.http_context.form)
        ctx._update_integer('SERVER_PORT', [], 1234)
        ref_parameters.update({'SERVER_PORT': 1234})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, integer and value in list
        self.assertIn('SERVER_PORT', self.http_context.form)
        ctx._update_integer('SERVER_PORT', [12, 7777, 654])
        ref_parameters.update({'SERVER_PORT': 7777})
        self.assertDictEqual(ref_parameters, ctx.parameters)

    def test_update_boolean(self):
        """ Test the _update_boolean method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # keep a copy of parameters
        ref_parameters = ctx.parameters.copy()
        # test with unknown parameter and no default value
        self.assertNotIn('dummy', self.http_context.form)
        ctx._update_boolean('dummy')
        ref_parameters.update({'dummy': False})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with unknown parameter and default value
        self.assertNotIn('dummy', self.http_context.form)
        ctx._update_boolean('dummy', True)
        ref_parameters.update({'dummy': True})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, no default value and unexpected value
        self.http_context.form['auto'] = 'unexpected value'
        ctx._update_boolean('auto')
        ref_parameters.update({'auto': False})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter, default value and unexpected value
        ctx._update_boolean('auto', True)
        ref_parameters.update({'auto': True})
        self.assertDictEqual(ref_parameters, ctx.parameters)
        # test with known parameter and expected value
        self.http_context.form['auto'] = '1'
        ctx._update_boolean('auto')
        ref_parameters.update({'auto': True})
        self.assertDictEqual(ref_parameters, ctx.parameters)

    def test_update_period(self):
        """ Test the update_period method. """
        from supvisors.viewcontext import ViewContext, PERIOD
        ctx = ViewContext(self.http_context)
        # test call
        with patch.object(ctx, '_update_integer') as mocked_update:
            ctx.update_period()
            self.assertEqual([call(PERIOD, DummyOptions().stats_periods,
                                   DummyOptions().stats_periods[0])],
                             mocked_update.call_args_list)

    def test_update_address(self):
        """ Test the update_address method. """
        from supvisors.viewcontext import ViewContext, ADDRESS
        ctx = ViewContext(self.http_context)
        # reset parameter because called in constructor
        del ctx.parameters[ADDRESS]
        # test call with valid value
        ctx.update_address()
        self.assertEqual('10.0.0.4', ctx.parameters[ADDRESS])
        # reset parameter
        del ctx.parameters[ADDRESS]
        # test call with invalid value
        self.http_context.form[ADDRESS] = '192.168.1.1'
        ctx.update_address()
        self.assertEqual('127.0.0.1', ctx.parameters[ADDRESS])

    def test_update_auto_refresh(self):
        """ Test the update_auto_refresh method. """
        from supvisors.viewcontext import ViewContext, AUTO
        ctx = ViewContext(self.http_context)
        # reset parameter because called in constructor
        del ctx.parameters[AUTO]
        # test call with default valid value
        ctx.update_auto_refresh()
        self.assertFalse(ctx.parameters[AUTO])
        # reset parameter
        del ctx.parameters[AUTO]
        # test call with other valid value
        self.http_context.form[AUTO] = 't'
        ctx.update_auto_refresh()
        self.assertTrue(ctx.parameters[AUTO])
        # reset parameter
        del ctx.parameters[AUTO]
        # test call with invalid value
        self.http_context.form[AUTO] = 'not a boolean'
        ctx.update_auto_refresh()
        self.assertFalse(ctx.parameters[AUTO])

    def test_update_application_name(self):
        """ Test the update_application_name method. """
        from supvisors.viewcontext import ViewContext, APPLI
        ctx = ViewContext(self.http_context)
        # reset parameter because called in constructor
        del ctx.parameters[APPLI]
        # test call with valid value
        ctx.context.applications = {'abc': [], 'dummy_appli': []}
        ctx.update_application_name()
        # cannot rely on ordering for second parameter because of dict need to split checking
        self.assertEqual('dummy_appli', ctx.parameters[APPLI])
        # reset parameter
        del ctx.parameters[APPLI]
        # test call with invalid value
        self.http_context.form[APPLI] = 'any_appli'
        ctx.update_application_name()
        self.assertEqual(None, ctx.parameters[APPLI])

    @patch('supvisors.viewcontext.ViewContext.get_address_stats', return_value=None)
    def test_update_process_name(self, mocked_stats):
        """ Test the update_process_name method. """
        from supvisors.viewcontext import ViewContext, PROCESS
        ctx = ViewContext(self.http_context)
        # reset parameter because called in constructor
        del ctx.parameters[PROCESS]
        # test call in case of address stats are not found
        ctx.update_process_name()
        self.assertEqual(None, ctx.parameters[PROCESS])
        # reset parameter
        del ctx.parameters[PROCESS]
        # test call when address stats are found and process in list
        mocked_stats.return_value = Mock(proc={('abc', 12): [], ('dummy_proc', 345): []})
        ctx.update_process_name()
        self.assertEqual('dummy_proc', ctx.parameters[PROCESS])
        # reset parameter
        del ctx.parameters[PROCESS]
        # test call when address stats are found and process not in list
        self.http_context.form[PROCESS] = 'any_proc'
        ctx.update_process_name()
        self.assertEqual(None, ctx.parameters[PROCESS])

    def test_update_namespec(self):
        """ Test the update_namespec method. """
        from supvisors.viewcontext import ViewContext, NAMESPEC
        ctx = ViewContext(self.http_context)
        # reset parameter because called in constructor
        del ctx.parameters[NAMESPEC]
        # test call with valid parameter
        ctx.context.processes = {'abc': [], 'dummy_proc': []}
        ctx.update_namespec()
        self.assertEqual('dummy_proc', ctx.parameters[NAMESPEC])
        # reset parameter
        del ctx.parameters[NAMESPEC]
        # test call with invalid value
        self.http_context.form[NAMESPEC] = 'any_proc'
        ctx.update_namespec()
        self.assertEqual(None, ctx.parameters[NAMESPEC])

    @patch('supvisors.viewcontext.ViewContext.get_nbcores', return_value=2)
    def test_update_cpu_id(self, _):
        """ Test the update_cpu_id method. """
        from supvisors.viewcontext import ViewContext, CPU
        ctx = ViewContext(self.http_context)
        # test call
        with patch.object(ctx, '_update_integer') as mocked_update:
            ctx.update_cpu_id()
            self.assertEqual([call(CPU, [0, 1, 2])],
                             mocked_update.call_args_list)

    @patch('supvisors.viewcontext.ViewContext.get_address_stats', return_value=None)
    def test_update_interface_name(self, mocked_stats):
        """ Test the update_interface_name method. """
        from supvisors.viewcontext import ViewContext, INTF
        ctx = ViewContext(self.http_context)
        # reset parameter because called in constructor
        del ctx.parameters[INTF]
        # test call in case of address stats are not found
        ctx.update_interface_name()
        self.assertEqual(None, ctx.parameters[INTF])
        # reset parameter
        del ctx.parameters[INTF]
        # test call when address stats are found and process in list
        mocked_stats.return_value = Mock(io={'lo': None})
        ctx.update_interface_name()
        self.assertEqual('lo', ctx.parameters[INTF])
        # reset parameter
        del ctx.parameters[INTF]
        # test call when address stats are found and process not in list
        mocked_stats.return_value = Mock(io={'lo': None, 'eth0': None})
        ctx.update_interface_name()
        self.assertEqual('eth0', ctx.parameters[INTF])

    def test_url_parameters(self):
        """ Test the url_parameters method. """
        # test default
        self.assertEqual('period=5&amp;strategy=CONFIG&amp;address=10.0.0.4', self.ctx.url_parameters())
        # update internal parameters
        self.ctx.parameters.update({'processname': 'dummy_proc',
                                    'namespec': 'dummy_ns',
                                    'address': '10.0.0.1',
                                    'cpuid': 3,
                                    'intfname': 'eth0',
                                    'appliname': 'dummy_appli',
                                    'period': 8,
                                    'strategy': 'CONFIG'})
        # test without additional parameters
        url = self.ctx.url_parameters()
        # result depends on dict contents so ordering is unreliable
        regexp = r'&amp;'.join([self.url_attr_template for _ in range(8)])
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertSequenceEqual(sorted(matches.groups()),
                                 sorted(('processname=dummy_proc',
                                         'namespec=dummy_ns',
                                         'address=10.0.0.1',
                                         'cpuid=3',
                                         'intfname=eth0',
                                         'appliname=dummy_appli',
                                         'period=8',
                                         'strategy=CONFIG')))
        # test with additional parameters
        url = self.ctx.url_parameters(**{'address': '127.0.0.1', 'intfname': 'lo', 'extra': 'args'})
        regexp = r'&amp;'.join([self.url_attr_template for _ in range(9)])
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertSequenceEqual(sorted(matches.groups()),
                                 sorted(('processname=dummy_proc',
                                         'namespec=dummy_ns',
                                         'address=127.0.0.1',
                                         'cpuid=3',
                                         'intfname=lo',
                                         'extra=args',
                                         'appliname=dummy_appli',
                                         'period=8',
                                         'strategy=CONFIG')))

    def test_format_url(self):
        """ Test the format_url method. """
        # test without address or arguments
        self.assertEqual('index.html?period=5&amp;strategy=CONFIG&amp;address=10.0.0.4',
                         self.ctx.format_url(0, 'index.html'))
        # test with address and arguments
        url = self.ctx.format_url('10.0.0.1', 'index.html',
                                  **{'period': 10, 'appliname': 'dummy_appli', 'extra': 'args'})
        # result depends on dict contents so ordering is unreliable
        base_address = r'http://10.0.0.1:7777/index.html\?'
        parameters = r'&amp;'.join([self.url_attr_template for _ in range(3)])
        regexp = base_address + parameters
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertSequenceEqual(sorted(matches.groups()),
                                 sorted(('extra=args',
                                         'period=10&amp;strategy=CONFIG&amp;address=10.0.0.4',
                                         'appliname=dummy_appli')))

    def test_message(self):
        """ Test the message method. """
        self.ctx.message(('warning', 'not as expected'))
        # result depends on dict contents so ordering is unreliable
        url = self.http_context.response['headers']['Location']
        base_address = r'http://10.0.0.1:7777/index.html\?'
        parameters = r'&amp;'.join([self.url_attr_template for _ in range(3)])
        regexp = base_address + parameters
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertSequenceEqual(sorted(matches.groups()),
                                 sorted(('message=not%20as%20expected',
                                         'period=5&amp;strategy=CONFIG&amp;address=10.0.0.4',
                                         'gravity=warning')))

    def test_get_nbcores(self):
        """ Test the get_nb_cores method. """
        # test default
        self.assertEqual(0, self.ctx.get_nbcores())
        # mock the structure
        stats = self.http_context.supervisord.supvisors.statistician
        stats.nbcores[self.ctx.local_address] = 4
        # test new call
        self.assertEqual(4, self.ctx.get_nbcores())
        # test with unknown address
        self.assertEqual(0, self.ctx.get_nbcores('10.0.0.1'))
        # test with known address
        stats.nbcores['10.0.0.1'] = 8
        self.assertEqual(8, self.ctx.get_nbcores('10.0.0.1'))

    def test_get_address_stats(self):
        """ Test the get_address_stats method. """
        from supvisors.viewcontext import PERIOD
        # test default
        self.assertIsNone(self.ctx.get_address_stats())
        # add statistics data
        stats_data = self.http_context.supervisord.supvisors.statistician.data
        stats_data['127.0.0.1'] = {5: 'data for period 5 at 127.0.0.1',
                                   8: 'data for period 8 at 127.0.0.1'}
        stats_data['10.0.0.1'] = {5: 'data for period 5 at 10.0.0.1',
                                  10: 'data for period 10 at 10.0.0.1'}
        # test with default address
        self.assertEqual('data for period 5 at 127.0.0.1', self.ctx.get_address_stats())
        # test with unknown address parameter
        self.assertIsNone(self.ctx.get_address_stats('10.0.0.2'))
        # test with known address parameter and existing period
        self.assertEqual('data for period 5 at 10.0.0.1', self.ctx.get_address_stats('10.0.0.1'))
        # update period
        self.ctx.parameters[PERIOD] = 8
        # test with default address and existing period
        self.assertEqual('data for period 8 at 127.0.0.1', self.ctx.get_address_stats())
        # test with known address parameter but missing period
        self.assertIsNone(self.ctx.get_address_stats('10.0.0.1'))

    def test_get_process_last_desc(self):
        """ Test the get_process_last_desc method. """
        # build common Mock
        mocked_process = Mock(addresses=set(),
                              infos={'10.0.0.1': {'local_time': 10, 'description': 'desc1'},
                                     '10.0.0.2': {'local_time': 30, 'description': 'desc2'},
                                     '10.0.0.3': {'local_time': 20, 'description': 'desc3'}})
        # test method return on non-running process and running requested
        with patch('supvisors.viewcontext.ViewContext.get_process_status',
                   return_value=mocked_process):
            self.assertTupleEqual((None, None),
                                  self.ctx.get_process_last_desc('dummy_proc', True))
        # test method return on non-running process and running not requested
        # the method returns the
        with patch('supvisors.viewcontext.ViewContext.get_process_status', return_value=mocked_process):
            self.assertTupleEqual(('10.0.0.2', 'desc2'),
                                  self.ctx.get_process_last_desc('dummy_proc'))
        # test method return on running process and running requested
        mocked_process.addresses.add('10.0.0.3')
        with patch('supvisors.viewcontext.ViewContext.get_process_status', return_value=mocked_process):
            self.assertTupleEqual(('10.0.0.3', 'desc3'),
                                  self.ctx.get_process_last_desc('dummy_proc', True))
        # test method return on running process and running not requested
        # same result as previous
        with patch('supvisors.viewcontext.ViewContext.get_process_status', return_value=mocked_process):
            self.assertTupleEqual(('10.0.0.3', 'desc3'),
                                  self.ctx.get_process_last_desc('dummy_proc'))
        # test method return on multiple running processes and running requested
        mocked_process.addresses.add('10.0.0.2')
        with patch('supvisors.viewcontext.ViewContext.get_process_status', return_value=mocked_process):
            self.assertTupleEqual(('10.0.0.2', 'desc2'),
                                  self.ctx.get_process_last_desc('dummy_proc', True))
        # test method return on running process and running not requested
        # same result as previous
        with patch('supvisors.viewcontext.ViewContext.get_process_status', return_value=mocked_process):
            self.assertTupleEqual(('10.0.0.2', 'desc2'),
                                  self.ctx.get_process_last_desc('dummy_proc'))

    @patch('supvisors.viewcontext.ViewContext.get_nbcores', return_value=4)
    def test_get_process_stats(self, mocked_core):
        """ Test the get_process_stats method. """
        # reset mocks that have been called in constructor
        mocked_core.reset_mock()
        # patch get_address_stats so that it returns no result
        with patch.object(self.ctx, 'get_address_stats', return_value=None) as mocked_stats:
            self.assertEqual((4, None), self.ctx.get_process_stats('dummy_proc'))
            self.assertEqual([call('127.0.0.1')], mocked_stats.call_args_list)
        mocked_core.reset_mock()
        # patch get_address_stats
        mocked_find = Mock(**{'find_process_stats.return_value': 'mock stats'})
        with patch.object(self.ctx, 'get_address_stats', return_value=mocked_find) as mocked_stats:
            self.assertEqual((4, 'mock stats'), self.ctx.get_process_stats('dummy_proc', '10.0.0.1'))
            self.assertEqual([call('10.0.0.1')], mocked_stats.call_args_list)
            self.assertEqual([call('10.0.0.1')], mocked_core.call_args_list)
            self.assertEqual([call('dummy_proc')], mocked_find.find_process_stats.call_args_list)

    def test_get_process_status(self):
        """ Test the get_process_status method. """
        from supvisors.viewcontext import NAMESPEC
        # test with empty context and no process in http form
        self.assertFalse(self.ctx.get_process_status())
        self.assertFalse(self.ctx.get_process_status('abc'))
        # test with context
        with patch.dict(self.ctx.context.processes,
                        {'abc': {'process': 'abc'},
                         'dummy_proc': {'process': 'dummy_proc'}},
                        clear=True):
            # test with nothing in http form
            self.assertFalse(self.ctx.get_process_status())
            self.assertDictEqual({'process': 'abc'}, self.ctx.get_process_status('abc'))
            # test with namespec in http form
            self.ctx.parameters[NAMESPEC] = 'abc'
            self.assertDictEqual({'process': 'abc'}, self.ctx.get_process_status())
            self.assertDictEqual({'process': 'dummy_proc'}, self.ctx.get_process_status('dummy_proc'))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])


if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
