#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from mock import patch
from StringIO import StringIO

from supvisors.tests.base import MockedSupvisors
from supvisors.tests.configurations import InvalidXmlTest, XmlTest


class ParserTest(unittest.TestCase):
    """ Test case for the sparser module. """

    def setUp(self):
        """ Create a ldummy supvisors structure. """
        self.supvisors = MockedSupvisors()

    @patch('lxml.etree.parse', side_effect=ImportError)
    @patch('xml.etree.ElementTree.parse', side_effect=ImportError)
    def test_no_parser(self, *args, **keywargs):
        """ Test the exception when no parser is available. """
        from supvisors.sparser import Parser
        with self.assertRaises(ImportError):
            Parser(self.supvisors)

    def test_valid_lxml(self):
        """ Test the parsing using lxml (optional dependency). """
        from supvisors.sparser import Parser
        with patch.object(self.supvisors.options, 'deployment_file', StringIO(XmlTest)):
            parser = Parser(self.supvisors)
        self.check_valid(parser)

    def test_invalid_lxml(self):
        """ Test the parsing of an invalid XML using lxml (optional dependency). """
        from supvisors.sparser import Parser
        with patch.object(self.supvisors.options, 'deployment_file', StringIO(InvalidXmlTest)):
            with self.assertRaises(ValueError):
                Parser(self.supvisors)

    @patch('lxml.etree.parse', side_effect=ImportError)
    def test_valid_element_tree(self, *args, **keywargs):
        """ Test the parsing of a valid XML using ElementTree (Supervisor dependency). """
        from supvisors.sparser import Parser
        # create Parser instance
        with patch.object(self.supvisors.options, 'deployment_file', StringIO(XmlTest)):
            parser = Parser(self.supvisors)
        self.check_valid(parser)

    @patch('lxml.etree.parse', side_effect=ImportError)
    def test_invalid_element_tree(self, *args, **keywargs):
        """ Test the parsing of an invalid XML using ElementTree (Supervisor dependency). """
        from supvisors.sparser import Parser
        # create Parser instance
        with patch.object(self.supvisors.options, 'deployment_file', StringIO(InvalidXmlTest)):
            parser = Parser(self.supvisors)
        self.check_invalid(parser)

    def check_valid(self, parser):
        """ Test the parsing of a valid XML. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        from supvisors.ttypes import StartingFailureStrategies
        # test models & patterns
        self.assertItemsEqual(['dummy_model_01', 'dummy_model_02', 'dummy_model_03', 'dummy_model_04'],
            parser.models.keys())
        self.assertItemsEqual(['dummies_', 'dummies_01_', 'dummies_02_'], parser.patterns.keys())
        # check unknown application
        application = ApplicationStatus('dummy_application_X', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_default_application_rules(application.rules)
        # check first application
        application = ApplicationStatus('dummy_application_A', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_default_application_rules(application.rules)
        # check second application
        application = ApplicationStatus('dummy_application_B', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_application_rules(application.rules, 1, 4, StartingFailureStrategies.STOP)
        # check third application
        application = ApplicationStatus('dummy_application_C', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_application_rules(application.rules, 20, 0, StartingFailureStrategies.ABORT)
        # check fourth application
        application = ApplicationStatus('dummy_application_D', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_application_rules(application.rules, 0, 100, StartingFailureStrategies.CONTINUE)
        # check program from unknown application: all default
        process = ProcessStatus('dummy_application_X', 'dummy_program_X0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check unknown program from known application: all default
        process = ProcessStatus('dummy_application_A', 'dummy_program_A0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check known program from known but not related application: all default
        process = ProcessStatus('dummy_application_A', 'dummy_program_B1', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check known empty program
        process = ProcessStatus('dummy_application_B', 'dummy_program_B0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check dash addresses and valid other values
        process = ProcessStatus('dummy_application_B', 'dummy_program_B1', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['#'], 3, 50, True, False, 5)
        # check single address with required not applicable and out of range loading
        process = ProcessStatus('dummy_application_B', 'dummy_program_B2', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.3'], 0, 0, False, False, 1)
        # check wildcard address, optional and max loading
        process = ProcessStatus('dummy_application_B', 'dummy_program_B3', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['*'], 0, 0, False, False, 100)
        # check multiple addresses, all other incorrect values
        process = ProcessStatus('dummy_application_B', 'dummy_program_B4', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.3', '10.0.0.1', '10.0.0.5'], 0, 0, False, False, 1)
        # check empty reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check unknown reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C1', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check known reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C2', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['*'], 0, 0, False, False, 25)
        # check other known reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C3', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['#'], 1, 0, True, True, 1)
        # check pattern with single matching and reference
        process = ProcessStatus('dummy_application_D', 'dummies_any', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.4', '10.0.0.2'], 0, 100, False, False, 10)
        # check pattern with multiple matching and configuration
        process = ProcessStatus('dummy_application_D', 'dummies_01_any', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['#'], 1, 1, False, True, 75)
        # check pattern with multiple matching and incorrect reference
        process = ProcessStatus('dummy_application_D', 'any_dummies_02_', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)

    def check_invalid(self, parser):
        """ Test the parsing of an invalid XML. """
        from supvisors.application import ApplicationStatus
        from supvisors.process import ProcessStatus
        from supvisors.ttypes import StartingFailureStrategies
        # test models & patterns
        self.assertItemsEqual(['dummy_model_01', 'dummy_model_02', 'dummy_model_03', 'dummy_model_04'],
            parser.models.keys())
        self.assertItemsEqual(['dummies_', 'dummies_01_', 'dummies_02_'], parser.patterns.keys())
        # check unknown application
        application = ApplicationStatus('dummy_application_X', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_default_application_rules(application.rules)
        # check first application
        application = ApplicationStatus('dummy_application_A', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_default_application_rules(application.rules)
        # check second application
        application = ApplicationStatus('dummy_application_B', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_application_rules(application.rules, 1, 4, StartingFailureStrategies.STOP)
        # check third application
        application = ApplicationStatus('dummy_application_C', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_application_rules(application.rules, 20, 0, StartingFailureStrategies.ABORT)
        # check fourth application
        application = ApplicationStatus('dummy_application_D', self.supvisors.logger)
        parser.load_application_rules(application)
        self.assert_application_rules(application.rules, 0, 100, StartingFailureStrategies.CONTINUE)
        # check program from unknown application: all default
        process = ProcessStatus('dummy_application_X', 'dummy_program_X0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check unknown program from known application: all default
        process = ProcessStatus('dummy_application_A', 'dummy_program_A0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check known program from known but not related application: all default
        process = ProcessStatus('dummy_application_A', 'dummy_program_B1', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check known empty program
        process = ProcessStatus('dummy_application_B', 'dummy_program_B0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check dash addresses and valid other values
        process = ProcessStatus('dummy_application_B', 'dummy_program_B1', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['#'], 3, 50, True, False, 5)
        # check single address with required not applicable and out of range loading
        process = ProcessStatus('dummy_application_B', 'dummy_program_B2', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.3'], 0, 0, False, False, 1)
        # check wildcard address, optional and max loading
        process = ProcessStatus('dummy_application_B', 'dummy_program_B3', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['*'], 0, 0, False, False, 100)
        # check multiple addresses, all other incorrect values
        process = ProcessStatus('dummy_application_B', 'dummy_program_B4', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.1', '10.0.0.2'], 0, 0, False, False, 1)
        # check multiple addresses, all other incorrect values
        process = ProcessStatus('dummy_application_B', 'dummy_program_B5', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.3', '10.0.0.1', '10.0.0.5'], 0, 0, False, False, 1)
        # check empty reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C0', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check unknown reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C1', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)
        # check known reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C2', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['*'], 0, 0, False, False, 25)
        # check other known reference
        process = ProcessStatus('dummy_application_C', 'dummy_program_C3', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['#'], 1, 0, True, True, 1)
        # check other known reference with additional unexpected configuration
        process = ProcessStatus('dummy_application_C', 'dummy_program_C4', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.4', '10.0.0.2'], 0, 100, False, False, 10)
        # check pattern with single matching and reference
        process = ProcessStatus('dummy_application_D', 'dummies_any', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['10.0.0.4', '10.0.0.2'], 0, 100, False, False, 10)
        # check pattern with multiple matching and configuration
        process = ProcessStatus('dummy_application_D', 'dummies_01_any', self.supvisors)
        parser.load_process_rules(process)
        self.assert_process_rules(process.rules, ['#'], 1, 1, False, True, 75)
        # check pattern with multiple matching and incorrect reference
        process = ProcessStatus('dummy_application_D', 'any_dummies_02_', self.supvisors)
        parser.load_process_rules(process)
        self.assert_default_process_rules(process.rules)

    def assert_default_application_rules(self, rules):
        """ Check that rules contains default values. """
        from supvisors.ttypes import StartingFailureStrategies
        self.assert_application_rules(rules, 0, 0, StartingFailureStrategies.ABORT)

    def assert_application_rules(self, rules, start, stop, strategy):
        """ Test the application rules. """
        self.assertEqual(start, rules.start_sequence)
        self.assertEqual(stop, rules.stop_sequence)
        self.assertEqual(strategy, rules.starting_failure_strategy)

    def assert_default_process_rules(self, rules):
        """ Check that rules contains default values. """
        self.assert_process_rules(rules, ['*'], 0, 0, False, False, 1)

    def assert_process_rules(self, rules, addresses, start, stop, required, wait, loading):
        """ Test the process rules. """
        self.assertListEqual(addresses, rules.addresses)
        self.assertEqual(start, rules.start_sequence)
        self.assertEqual(stop, rules.stop_sequence)
        self.assertEqual(required, rules.required)
        self.assertEqual(wait, rules.wait_exit)
        self.assertEqual(loading, rules.expected_loading)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
