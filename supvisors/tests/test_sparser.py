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

import pytest

from io import BytesIO

from supvisors.sparser import *
from supvisors.process import ProcessRules
from supvisors.ttypes import RunningFailureStrategies, StartingFailureStrategies

from .configurations import InvalidXmlTest, XmlTest


def assert_default_application_rules(rules):
    """ Check that rules contains default values. """
    assert_application_rules(rules, False, True, ['*'], 0, 0, StartingStrategies.CONFIG,
                             StartingFailureStrategies.ABORT, RunningFailureStrategies.CONTINUE)


def assert_application_rules(rules, managed, distributed, node_names, start, stop, starting_strategy,
                             starting_failure_strategy, running_failure_strategy):
    """ Check the application rules. """
    assert rules.managed == managed
    assert rules.distributed == distributed
    assert rules.node_names == node_names
    assert rules.start_sequence == start
    assert rules.stop_sequence == stop
    assert rules.starting_strategy == starting_strategy
    assert rules.starting_failure_strategy == starting_failure_strategy
    assert rules.running_failure_strategy == running_failure_strategy


def assert_default_process_rules(rules):
    """ Check that rules contains default values. """
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 0, RunningFailureStrategies.CONTINUE)


def assert_process_rules(rules, nodes, hash_nodes, start, stop, required,
                         wait, expected_load, running_strategy):
    """ Check the process rules. """
    assert rules.node_names == nodes
    assert rules.hash_node_names == hash_nodes
    assert rules.start_sequence == start
    assert rules.stop_sequence == stop
    assert rules.required == required
    assert rules.wait_exit == wait
    assert rules.expected_load == expected_load
    assert rules.running_failure_strategy == running_strategy


def load_application_rules(parser, application_name):
    rules = ApplicationRules()
    parser.load_application_rules(application_name, rules)
    return rules


def load_program_rules(parser, application_name, process_name):
    rules = ProcessRules(parser.supvisors)
    parser.load_program_rules('%s:%s' % (application_name, process_name), rules)
    return rules


def check_aliases_valid(parser):
    """ Test the Parser.check_node_list on the basis of the aliases found in Valid XML. """
    assert parser.check_node_list('nodes_model_03') == ['10.0.0.4', '10.0.0.2']
    assert parser.check_node_list('10.0.0.1,nodes_model_03') == ['10.0.0.1', '10.0.0.4', '10.0.0.2']
    assert parser.check_node_list('10.0.0.5,nodes_appli_D,10.0.0.1') == ['10.0.0.5', '10.0.0.1']
    assert parser.check_node_list('192.17.8.2,nodes_model_03') == ['10.0.0.4', '10.0.0.2']
    assert parser.check_node_list('192.17.8.2,nodes_model_03,*') == ['*']
    assert parser.check_node_list('not used,10.0.0.3') == ['10.0.0.2', '10.0.0.3']


def check_valid(parser):
    """ Test the parsing of a valid XML. """
    # test aliases, models & patterns
    assert parser.aliases == {'nodes_model_03': ['10.0.0.4', '10.0.0.2'], 'nodes_appli_D': ['10.0.0.1', '10.0.0.5'],
                              'not used': ['10.0.0.2', 'nodes_appli_D']}
    check_aliases_valid(parser)
    assert sorted(parser.models.keys()) == ['dummy_model_01', 'dummy_model_02',
                                            'dummy_model_03', 'dummy_model_04', 'dummy_model_05']
    assert parser.printable_program_patterns() == {'application_D': ['dummies_', 'dummies_01_', 'dummies_02_']}
    # check unknown application
    rules = load_application_rules(parser, 'dummy_application_X')
    assert_default_application_rules(rules)
    # check first application
    rules = load_application_rules(parser, 'dummy_application_A')
    assert_application_rules(rules, True, True, ['*'], 0, 0, StartingStrategies.CONFIG,
                             StartingFailureStrategies.ABORT, RunningFailureStrategies.CONTINUE)
    # check second application
    rules = load_application_rules(parser, 'dummy_application_B')
    assert_application_rules(rules, True, False, ['*'], 1, 4, StartingStrategies.CONFIG,
                             StartingFailureStrategies.STOP, RunningFailureStrategies.RESTART_PROCESS)
    # check third application
    rules = load_application_rules(parser, 'dummy_application_C')
    assert_application_rules(rules, True, True, ['*'], 20, 0, StartingStrategies.LOCAL,
                             StartingFailureStrategies.ABORT, RunningFailureStrategies.STOP_APPLICATION)
    # check fourth application
    rules = load_application_rules(parser, 'dummy_application_D')
    print(rules)
    assert_application_rules(rules, True, False, ['10.0.0.1', '10.0.0.5'], 0, 100, StartingStrategies.LESS_LOADED,
                             StartingFailureStrategies.CONTINUE, RunningFailureStrategies.RESTART_APPLICATION)
    # check loop application
    rules = load_application_rules(parser, 'dummy_application_E')
    assert_application_rules(rules, True, True,  ['*'], 0, 0,  StartingStrategies.MOST_LOADED,
                             StartingFailureStrategies.ABORT, RunningFailureStrategies.CONTINUE)
    # check program from unknown application: all default
    rules = load_program_rules(parser, 'dummy_application_X', 'dummy_program_X0')
    assert_default_process_rules(rules)
    # check unknown program from known application: all default
    rules = load_program_rules(parser, 'dummy_application_A', 'dummy_program_A0')
    assert_default_process_rules(rules)
    # check known program from known but not related application: all default
    rules = load_program_rules(parser, 'dummy_application_A', 'dummy_program_B1')
    assert_default_process_rules(rules)
    # check known empty program
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B0')
    assert_default_process_rules(rules)
    # check dash addresses and valid other values
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B1')
    assert_process_rules(rules, [], ['*'], 3, 50, True, False, 5,
                         RunningFailureStrategies.CONTINUE)
    # check single address with required not applicable and out of range loading
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B2')
    assert_process_rules(rules, ['10.0.0.3'], [], 0, 0, False, False, 0,
                         RunningFailureStrategies.RESTART_PROCESS)
    # check wildcard address, optional and max loading
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B3')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 100,
                         RunningFailureStrategies.STOP_APPLICATION)
    # check multiple addresses, all other incorrect values
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B4')
    assert_process_rules(rules, ['10.0.0.3', '10.0.0.1', '10.0.0.5'], [], 0, 0, False, False, 0,
                         RunningFailureStrategies.RESTART_APPLICATION)
    # check empty reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C0')
    assert_default_process_rules(rules)
    # check unknown reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C1')
    assert_default_process_rules(rules)
    # check known reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C2')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 25,
                         RunningFailureStrategies.STOP_APPLICATION)
    # check other known reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C3')
    assert_process_rules(rules, [], ['*'], 1, 0, True, True, 0,
                         RunningFailureStrategies.CONTINUE)
    # check pattern with single matching and reference
    rules = load_program_rules(parser, 'dummy_application_D', 'dummies_any')
    assert_process_rules(rules, ['10.0.0.4', '10.0.0.2'], [], 50, 100, False, False, 10,
                         RunningFailureStrategies.CONTINUE)
    # check pattern with multiple matching and configuration
    rules = load_program_rules(parser, 'dummy_application_D', 'dummies_01_any')
    assert_process_rules(rules, [], ['10.0.0.1', '10.0.0.5'], 1, 1, False, True, 75,
                         RunningFailureStrategies.CONTINUE)
    # check pattern with multiple matching and incorrect reference (model calling for another model)
    # this is valid since Supvisors 0.5
    rules = load_program_rules(parser, 'dummy_application_D', 'any_dummies_02_')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 20,
                         RunningFailureStrategies.STOP_APPLICATION)
    # check multiple reference (over the maximum defined)
    # almost all rules set to default, despite enf of chain is on dummy_model_01
    rules = load_program_rules(parser, 'dummy_application_E', 'dummy_program_E')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 15,
                         RunningFailureStrategies.CONTINUE)


def check_aliases_invalid(parser):
    assert parser.check_node_list('nodes_prg_B1') == ['#']
    assert parser.check_node_list('nodes_appli_D') == []
    assert parser.check_node_list('nodes_prg_B3,10.0.0.1') == ['*']
    assert parser.check_node_list('10.0.0.5,not used too') == ['10.0.0.5', '10.0.0.1', '#']
    assert parser.check_node_list('10.0.0.5,not used') == ['*']


def check_invalid(parser):
    """ Test the parsing of an invalid XML. """
    # test aliases, models & patterns
    assert parser.aliases == {'not used': ['nodes_prg_B3', 'nodes_appli_D'],
                              'not used too': ['#', '10.0.0.1', '192.168.12.20'], 'nodes_prg_B1': ['#'],
                              'nodes_prg_B3': ['*', '10.0.0.4', '192.168.12.20'], 'nodes_appli_D': ['']}
    check_aliases_invalid(parser)
    assert sorted(parser.models.keys()) == ['dummy_model_01', 'dummy_model_02', 'dummy_model_03', 'dummy_model_04']
    assert parser.printable_program_patterns() == {'dummy_application_D': ['dummies_', 'dummies_01_', 'dummies_02_']}
    # check unknown application
    rules = load_application_rules(parser, 'dummy_application_X')
    assert_default_application_rules(rules)
    # check first application
    rules = load_application_rules(parser, 'dummy_application_A')
    assert_application_rules(rules, True, True, ['*'], 0, 0, StartingStrategies.CONFIG,
                             StartingFailureStrategies.ABORT, RunningFailureStrategies.CONTINUE)
    # check second application
    rules = load_application_rules(parser, 'dummy_application_B')
    assert_application_rules(rules, True, True, ['*'], 1, 4, StartingStrategies.CONFIG,
                             StartingFailureStrategies.STOP, RunningFailureStrategies.RESTART_PROCESS)
    # check third application
    rules = load_application_rules(parser, 'dummy_application_C')
    assert_application_rules(rules, True, False, ['*'], 20, 0, StartingStrategies.CONFIG,
                             StartingFailureStrategies.ABORT, RunningFailureStrategies.STOP_APPLICATION)
    # check fourth application
    rules = load_application_rules(parser, 'dummy_application_D')
    assert_application_rules(rules, True, True, ['*'], 0, 100, StartingStrategies.CONFIG,
                             StartingFailureStrategies.CONTINUE, RunningFailureStrategies.RESTART_APPLICATION)
    # check program from unknown application: all default
    rules = load_program_rules(parser, 'dummy_application_X', 'dummy_program_X0')
    assert_default_process_rules(rules)
    # check unknown program from known application: all default
    rules = load_program_rules(parser, 'dummy_application_A', 'dummy_program_A0')
    assert_default_process_rules(rules)
    # check known program from known but not related application: all default
    rules = load_program_rules(parser, 'dummy_application_A', 'dummy_program_B1')
    assert_default_process_rules(rules)
    # check known empty program
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B0')
    assert_default_process_rules(rules)
    # check dash addresses and valid other values
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B1')
    assert_process_rules(rules, [], ['*'], 3, 50, True, False, 5, RunningFailureStrategies.CONTINUE)
    # check single address with required not applicable and out of range loading
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B2')
    assert_process_rules(rules, ['10.0.0.3'], [], 0, 0, False, False, 0, RunningFailureStrategies.RESTART_PROCESS)
    # check wildcard address, optional and max loading
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B3')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 100, RunningFailureStrategies.STOP_APPLICATION)
    # check multiple addresses, all other incorrect values
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B4')
    assert_process_rules(rules, ['10.0.0.1', '10.0.0.2'], [], 0, 0, False, False, 0,
                         RunningFailureStrategies.RESTART_APPLICATION)
    # check multiple addresses, all other incorrect values
    rules = load_program_rules(parser, 'dummy_application_B', 'dummy_program_B5')
    assert_process_rules(rules, ['10.0.0.3', '10.0.0.1', '10.0.0.5'], [], 0, 0, False, False, 0,
                         RunningFailureStrategies.CONTINUE)
    # check empty reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C0')
    assert_default_process_rules(rules)
    # check unknown reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C1')
    assert_default_process_rules(rules)
    # check known reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C2')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 25, RunningFailureStrategies.STOP_APPLICATION)
    # check other known reference
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C3')
    assert_process_rules(rules, [], ['*'], 1, 0, True, True, 0, RunningFailureStrategies.CONTINUE)
    # check other known reference with additional unexpected configuration
    # WARN: this is valid since Supvisors 0.5
    rules = load_program_rules(parser, 'dummy_application_C', 'dummy_program_C4')
    assert_process_rules(rules, [], ['*'], 3, 100, True, False, 5, RunningFailureStrategies.CONTINUE)
    # check pattern with single matching and reference
    # check that existing values are not reset
    rules = ProcessRules(parser.supvisors)
    rules.running_failure_strategy = RunningFailureStrategies.RESTART_APPLICATION
    parser.load_program_rules('dummy_application_D:dummies_any', rules)
    assert_process_rules(rules, ['10.0.0.4', '10.0.0.2'], [], 0, 100, False, False, 10,
                         RunningFailureStrategies.RESTART_APPLICATION)
    # check pattern with multiple matching and configuration
    rules = load_program_rules(parser, 'dummy_application_D', 'dummies_01_any')
    assert_process_rules(rules, [], ['*'], 1, 1, False, True, 75, RunningFailureStrategies.CONTINUE)
    # check pattern with multiple matching and recursive reference
    # WARN: this is valid since Supvisors 0.5
    rules = load_program_rules(parser, 'dummy_application_D', 'any_dummies_02_')
    assert_process_rules(rules, ['*'], [], 0, 0, False, False, 25, RunningFailureStrategies.STOP_APPLICATION)


@pytest.fixture
def lxml_import():
    return pytest.importorskip('lxml')


def test_valid_lxml(mocker, lxml_import, supvisors):
    """ Test the parsing using lxml (optional dependency). """
    mocker.patch.object(supvisors.options, 'rules_file', BytesIO(XmlTest))
    parser = Parser(supvisors)
    check_valid(parser)


def test_invalid_lxml(mocker, supvisors):
    """ Test the parsing of an invalid XML using lxml (optional dependency). """
    mocker.patch('supvisors.sparser.stderr')
    mocker.patch.object(supvisors.options, 'rules_file', BytesIO(InvalidXmlTest))
    with pytest.raises(ValueError):
        Parser(supvisors)


@pytest.fixture
def lxml_fail_import(mocker):
    """ Mock ImportError on optional lxml if installed to force ElementTree testing. """
    mocker.patch.dict('sys.modules', {'lxml.etree': None})


def test_no_parser(mocker, supvisors, lxml_fail_import):
    """ Test the exception when no parser is available. """
    mocker.patch('xml.etree.ElementTree.parse', side_effect=ImportError)
    # create Parser instance
    with pytest.raises(ImportError):
        Parser(supvisors)


def test_valid_element_tree(mocker, supvisors, lxml_fail_import):
    """ Test the parsing of a valid XML using ElementTree. """
    # create Parser instance
    mocker.patch.object(supvisors.options, 'rules_file', BytesIO(XmlTest))
    parser = Parser(supvisors)
    check_valid(parser)


def test_invalid_element_tree(mocker, supvisors, lxml_fail_import):
    """ Test the parsing of an invalid XML using ElementTree. """
    # create Parser instance
    mocker.patch.object(supvisors.options, 'rules_file', BytesIO(InvalidXmlTest))
    parser = Parser(supvisors)
    check_invalid(parser)
