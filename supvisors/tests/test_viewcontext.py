#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from mock import call, patch, Mock

from supvisors.tests.base import (DummyAddressMapper,
                                  DummyHttpContext,
                                  DummyOptions)


class ViewContextTest(unittest.TestCase):
    """ Test case for the viewcontext module. """

    url_attr_template = r'(.+=.+)'

    def setUp(self):
        """ Create a logger that stores log traces. """
        self.http_context = DummyHttpContext('')

    def test_init(self):
        """ Test the values set at construction. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertIs(ctx.http_context, self.http_context)
        self.assertIs(ctx.supvisors, self.http_context.supervisord.supvisors)
        self.assertEqual(DummyAddressMapper().local_address, ctx.address)
        self.assertDictEqual({'namespec': None,
                              'period': 5,
                              'appliname': None,
                              'processname': None,
                              'cpuid': 0,
                              'intfname': None}, ctx.parameters)

    def test_get_server_port(self):
        """ Test the get_server_port method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertEqual(7777, ctx.get_server_port())

    def test_get_action(self):
        """ Test the get_action method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertEqual('test', ctx.get_action())

    def test_get_address(self):
        """ Test the get_address method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertEqual('10.0.0.4', ctx.get_address())

    def test_get_message(self):
        """ Test the get_message method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertEqual('hi chaps', ctx.get_message())

    def test_get_gravity(self):
        """ Test the get_gravity method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertEqual('none', ctx.get_gravity())

    def test_url_parameters(self):
        """ Test the get_nb_cores method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # test default
        self.assertEqual(ctx.url_parameters(),
                         'period=5')
        # update internal parameters
        ctx.parameters.update({'processname': 'dummy_proc',
                               'namespec': 'dummy_ns',
                               'address': '10.0.0.1',
                               'cpuid': 3,
                               'intfname': 'eth0',
                               'appliname': 'dummy_appli',
                               'period': 8})
        # test default
        self.assertEqual(ctx.url_parameters(),
                         'processname=dummy_proc&amp;namespec=dummy_ns&amp;'
                         'address=10.0.0.1&amp;cpuid=3&amp;intfname=eth0&amp;'
                         'appliname=dummy_appli&amp;period=8')
        # test with extra arguments, overloading some
        self.assertEqual(ctx.url_parameters(**{'extra': 'args',
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
            self.assertEqual(str(idx-1), ViewContext.cpu_id_to_string(idx))
        self.assertEqual('all', ViewContext.cpu_id_to_string(0))
        self.assertEqual('all', ViewContext.cpu_id_to_string(-5))

    def test_update_string(self):
        """ Test the _update_string method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # keep a copy of parmeters
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
        # keep a copy of parmeters
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

    @patch('supvisors.viewcontext.ViewContext._update_string')
    def test_update_application_name(self, mocked_update):
        """ Test the update_application_name method. """
        from supvisors.viewcontext import ViewContext, APPLI
        ctx = ViewContext(self.http_context)
        # reset mock because called in constructor
        mocked_update.reset_mock()
        # test call
        with patch.dict(ctx.context.applications,
                        {'abc': [], 'dummy_appli':[]}, clear=True):
            ctx.update_application_name()
        # cannot rely on ordering for second parameter because of dict
        # need to split checking
        self.assertEqual(1, mocked_update.call_count)
        mocked_call = mocked_update.call_args[0]
        self.assertEqual(APPLI, mocked_call[0])
        self.assertItemsEqual(['abc', 'dummy_appli'], mocked_call[1])

    @patch('supvisors.viewcontext.ViewContext.get_address_stats',
           return_value=None)
    @patch('supvisors.viewcontext.ViewContext._update_string')
    def test_update_process_name(self, mocked_update, mocked_stats):
        """ Test the update_process_name method. """
        from supvisors.viewcontext import ViewContext, PROCESS
        ctx = ViewContext(self.http_context)
        # reset mock because called in constructor
        mocked_update.reset_mock()
        # test call in case of process stats are not found
        ctx.update_process_name()
        self.assertEqual([call(PROCESS, [])],
                         mocked_update.call_args_list)
        mocked_update.reset_mock()
        # test call in case of process stats not found
        mocked_stats.return_value = Mock(proc={('abc', 12): [],
                                               ('dummy_proc', 345): []})
        ctx.update_process_name()
        self.assertEqual(1, mocked_update.call_count)
        call_args = mocked_update.call_args[0]
        self.assertEqual(PROCESS, call_args[0])
        self.assertItemsEqual(['abc', 'dummy_proc'], call_args[1])

    @patch('supvisors.viewcontext.ViewContext._update_string')
    def test_update_namespec(self, mocked_update):
        """ Test the update_namespec method. """
        from supvisors.viewcontext import ViewContext, NAMESPEC
        ctx = ViewContext(self.http_context)
        # reset mock because called in constructor
        mocked_update.reset_mock()
        # test call
        with patch.dict(ctx.context.processes,
                        {'abc': [], 'dummy_proc':[]}, clear=True):
            ctx.update_namespec()
            self.assertEqual([call(NAMESPEC, ['abc', 'dummy_proc'])],
                             mocked_update.call_args_list)

    @patch('supvisors.viewcontext.ViewContext.get_nbcores', return_value=2)
    def test_update_cpu_id(self, mocked_nbcores):
        """ Test the update_cpu_id method. """
        from supvisors.viewcontext import ViewContext, CPU
        ctx = ViewContext(self.http_context)
        # test call
        with patch.object(ctx, '_update_integer') as mocked_update:
            ctx.update_cpu_id()
            self.assertEqual([call(CPU, [0, 1, 2])],
                             mocked_update.call_args_list)

    @patch('supvisors.viewcontext.ViewContext._update_string')
    def test_update_interface_name(self, mocked_update):
        """ Test the update_interface_name method. """
        from supvisors.viewcontext import ViewContext, INTF
        ctx = ViewContext(self.http_context)
        # reset mock because called in constructor
        mocked_update.reset_mock()
        # test call
        ctx.update_interface_name()
        self.assertEqual([call(INTF, [], None)],
                         mocked_update.call_args_list)

    def test_url_parameters(self):
        """ Test the url_parameters method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # test default
        self.assertEqual('period=5', ctx.url_parameters())
        # update internal parameters
        ctx.parameters.update({'processname': 'dummy_proc',
                               'namespec': 'dummy_ns',
                               'address': '10.0.0.1',
                               'cpuid': 3,
                               'intfname': 'eth0',
                               'appliname': 'dummy_appli',
                               'period': 8})
        # test without additional parameters
        url = ctx.url_parameters()
        # result depends on dict contents so ordering is unreliable
        regexp = r'&amp;'.join([self.url_attr_template for _ in range(7)])
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertItemsEqual(matches.groups(),
                              ('processname=dummy_proc',
                               'namespec=dummy_ns',
                               'address=10.0.0.1',
                               'cpuid=3',
                               'intfname=eth0',
                               'appliname=dummy_appli',
                               'period=8'))
        # test with additional parameters
        url = ctx.url_parameters(**{'address': '127.0.0.1',
                                    'intfname': 'lo',
                                    'extra': 'args'})
        regexp = r'&amp;'.join([self.url_attr_template for _ in range(8)])
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertItemsEqual(matches.groups(),
                              ('processname=dummy_proc',
                               'namespec=dummy_ns',
                               'address=127.0.0.1',
                               'cpuid=3',
                               'intfname=lo',
                               'extra=args',
                               'appliname=dummy_appli',
                               'period=8'))

    def test_format_url(self):
        """ Test the format_url method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # test without address or arguments
        self.assertEqual('index.html?period=5',
                         ctx.format_url(0, 'index.html'))
        # test with address and arguments
        url = ctx.format_url('10.0.0.1', 'index.html',
                             **{'period': 10,
                                'appliname': 'dummy_appli',
                                'extra': 'args'})
        # result depends on dict contents so ordering is unreliable
        base_address = r'http://10.0.0.1:7777/index.html\?'
        parameters = r'&amp;'.join([self.url_attr_template for _ in range(3)])
        regexp = base_address + parameters
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertItemsEqual(matches.groups(),
                              ('extra=args',
                               'period=10',
                               'appliname=dummy_appli'))

    def test_message(self):
        """ Test the message method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        self.assertIsNone(self.http_context.response['headers']['Location'])
        ctx.message(('warning', 'not as expected'))
        # result depends on dict contents so ordering is unreliable
        url = self.http_context.response['headers']['Location']
        base_address = r'http://10.0.0.1:7777/index.html\?'
        parameters = r'&amp;'.join([self.url_attr_template for _ in range(3)])
        regexp = base_address + parameters
        matches = re.match(regexp, url)
        self.assertIsNotNone(matches)
        self.assertItemsEqual(matches.groups(),
                              ('message=not%20as%20expected',
                               'period=5',
                               'gravity=warning'))

    def test_get_nbcores(self):
        """ Test the get_nb_cores method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # test default
        self.assertEqual(0, ctx.get_nbcores())
        # mock the structure
        stats = self.http_context.supervisord.supvisors.statistician
        stats.nbcores[ctx.address] = 4
        # test new call
        self.assertEqual(4, ctx.get_nbcores())
        # test with unknown address
        self.assertEqual(0, ctx.get_nbcores('10.0.0.1'))
        # test with known address
        stats.nbcores['10.0.0.1'] = 8
        self.assertEqual(8, ctx.get_nbcores('10.0.0.1'))

    def test_get_address_stats(self):
        """ Test the get_address_stats method. """
        from supvisors.viewcontext import ViewContext, PERIOD
        ctx = ViewContext(self.http_context)
        # test default
        self.assertIsNone(ctx.get_address_stats())
        # add statistics data
        stats_data = self.http_context.supervisord.supvisors.statistician.data
        stats_data['127.0.0.1'] = {5: 'data for period 5 at 127.0.0.1',
                                   8: 'data for period 8 at 127.0.0.1'}
        stats_data['10.0.0.1'] = {5: 'data for period 5 at 10.0.0.1',
                                  10: 'data for period 10 at 10.0.0.1'}
        # test with default address
        self.assertEqual('data for period 5 at 127.0.0.1',
                         ctx.get_address_stats())
        # test with unknown address parameter
        self.assertIsNone(ctx.get_address_stats('10.0.0.2'))
        # test with known address parameter and existing period
        self.assertEqual('data for period 5 at 10.0.0.1',
                         ctx.get_address_stats('10.0.0.1'))
        # update period
        ctx.parameters[PERIOD] = 8
        # test with default address and existing period
        self.assertEqual('data for period 8 at 127.0.0.1',
                         ctx.get_address_stats())
        # test with known address parameter but missing period
        self.assertIsNone(ctx.get_address_stats('10.0.0.1'))

    @patch('supvisors.viewcontext.ViewContext.get_nbcores',
           return_value=4)
    @patch('supvisors.viewcontext.ViewContext.get_process_status',
           return_value=Mock(addresses=[]))
    def test_get_process_stats(self, mocked_status, mocked_core):
        """ Test the get_process_stats method. """
        from supvisors.viewcontext import ViewContext
        ctx = ViewContext(self.http_context)
        # reset mocks as they have been called in constructor
        mocked_core.reset_mock()
        # patch get_address_stats
        mocked_find = Mock(**{'find_process_stats.return_value': 'mock stats'})
        with patch.object(ctx, 'get_address_stats', return_value=mocked_find) \
            as mocked_stats:
            # test with default running False
            self.assertEqual(('mock stats', 4),
                             ctx.get_process_stats('dummy_proc'))
            self.assertEqual([], mocked_status.call_args_list)
            self.assertEqual([call(ctx.address)], mocked_core.call_args_list)
            self.assertEqual([call('127.0.0.1')], mocked_stats.call_args_list)
            self.assertEqual([call('dummy_proc')],
                             mocked_find.find_process_stats.call_args_list)
            mocked_status.reset_mock()
            mocked_core.reset_mock()
            mocked_stats.reset_mock()
            mocked_find.reset_mock()
            # test with default running True, but corresponding to a process
            # that is stopped
            self.assertEqual(('mock stats', 4),
                             ctx.get_process_stats('dummy_proc', True))
            self.assertEqual([call('dummy_proc')], mocked_status.call_args_list)
            self.assertEqual([call(None)], mocked_core.call_args_list)
            self.assertEqual([call(None)], mocked_stats.call_args_list)
            self.assertEqual([call('dummy_proc')],
                             mocked_find.find_process_stats.call_args_list)
            mocked_status.reset_mock()
            mocked_core.reset_mock()
            mocked_stats.reset_mock()
            mocked_find.reset_mock()
            # test with default running True, but corresponding to a process
            # that is running
            mocked_status.return_value = Mock(addresses=['10.0.0.2',
                                                         '10.0.0.1'])
            self.assertEqual(('mock stats', 4),
                             ctx.get_process_stats('dummy_proc', True))
            self.assertEqual([call('dummy_proc')], mocked_status.call_args_list)
            self.assertEqual([call('10.0.0.2')], mocked_core.call_args_list)
            self.assertEqual([call('10.0.0.2')], mocked_stats.call_args_list)
            self.assertEqual([call('dummy_proc')],
                             mocked_find.find_process_stats.call_args_list)

    def test_get_process_status(self):
        """ Test the get_process_status method. """
        from supvisors.viewcontext import ViewContext, NAMESPEC
        ctx = ViewContext(self.http_context)
        # test with empty context and no process in http form
        self.assertFalse(ctx.get_process_status())
        self.assertFalse(ctx.get_process_status('abc'))
        # test with context
        with patch.dict(ctx.context.processes,
                        {'abc': {'process': 'abc'},
                         'dummy_proc': {'process': 'dummy_proc'}},
                        clear=True):
            # test with nothing in http form
            self.assertFalse(ctx.get_process_status())
            self.assertDictEqual({'process': 'abc'},
                                 ctx.get_process_status('abc'))
            # test with namespec in http form
            ctx.parameters[NAMESPEC] = 'abc'
            self.assertDictEqual({'process': 'abc'},
                                 ctx.get_process_status())
            self.assertDictEqual({'process': 'dummy_proc'},
                                 ctx.get_process_status('dummy_proc'))


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
