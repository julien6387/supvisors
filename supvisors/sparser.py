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

import re
from collections import OrderedDict
from distutils.util import strtobool
from os import path
from sys import stderr
from typing import Any, Dict, List, Optional, Tuple, Union

from supervisor.datatypes import list_of_strings
from supervisor.options import split_namespec

from .application import ApplicationRules
from .process import ProcessRules
from .ttypes import (DistributionRules, StartingStrategies, StartingFailureStrategies,
                     RunningFailureStrategies, EnumClassType)
from .utils import ATSIGN, HASHTAG, WILDCARD

# XSD for XML validation
supvisors_folder = path.dirname(__file__)
rules_xsd = path.join(supvisors_folder, 'rules.xsd')


class Parser(object):
    """ The Parser class used to get application and program rules from an XML file. """

    # for recursive references to program models, depth is limited to 3
    LOOP_CHECK = 3

    # annotation types
    AnyRules = Union[ApplicationRules, ProcessRules]

    def __init__(self, supvisors: Any) -> None:
        """ The constructor parses the XML file and stores references the models and patterns found.

        :param supvisors: the global Supvisors structure.
        """
        self.supvisors = supvisors
        self.logger = supvisors.logger
        # attributes
        self.roots = []
        self.aliases = {}
        self.models = {}
        self.application_patterns = {}
        self.program_patterns = {}
        # get a parser per rules file
        self.load_rules_files(supvisors.options.rules_files)

    def load_rules_files(self, rules_files: List[str]) -> None:
        """ Get roots, models and patterns from the rules files provided.

        :param rules_files: the list of rules files to load
        :return: None
        """
        for rules_file in rules_files:
            self.logger.info(f'Parser: parsing rules from {rules_file}')
            root = self.parse(rules_file).getroot()
            self.roots.append(root)
            # get aliases - keep string as it is easier to process
            self.aliases.update({element.get('name'): list_of_strings(element.text)
                                 for element in root.findall('./alias[@name]')
                                 if element.text})
            # get models
            elements = root.findall('./model[@name]')
            self.models.update({element.get('name'): element for element in elements})
            # get application patterns
            app_elements = root.findall('./application[@pattern]')
            self.application_patterns.update({app_element.get('pattern'): app_element
                                              for app_element in app_elements})
            # get program patterns sorted by application
            app_elements = root.findall('./application/programs/program[@pattern]/../..')
            for app_element in app_elements:
                prg_elements = app_element.findall('./programs/program[@pattern]')
                prg_patterns = self.program_patterns.setdefault(app_element, {})
                prg_patterns.update({prg_element.get('pattern'): prg_element
                                     for prg_element in prg_elements})
        # log what has been found
        self.logger.debug(f'Parser.load_rules_files: found aliases {self.aliases}')
        self.logger.debug(f'Parser.load_rules_files: found models {self.models.keys()}')
        self.logger.debug(f'Parser.load_rules_files: found application patterns {self.application_patterns.keys()}')
        self.logger.debug(f'Parser.load_rules_files: found program patterns {self.printable_program_patterns()}')

    def printable_program_patterns(self) -> Dict[str, List[str]]:
        """ Get a printable version of program patterns (without parser elements).

        :return: a list of program patterns per application name or patterns
        """
        return {Parser.get_element_name(app_element): list(prg_patterns.keys())
                for app_element, prg_patterns in self.program_patterns.items()}

    def load_application_rules(self, application_name: str, rules: ApplicationRules) -> None:
        """ Find an entry corresponding to the application in the rules file, then load the parameters found.

        :param application_name: the name of the application for which to find rules in the XML rules file
        :param rules: the application rules to load
        :return: None
        """
        # find application element using a xpath
        self.logger.trace(f'Parser.load_application_rules: searching application element for {application_name}')
        application_elt = self.get_application_element(application_name)
        if application_elt is not None:
            rules.managed = True
            self.load_enum(application_elt, 'distribution', DistributionRules, rules)
            self.load_identifiers(application_elt, rules)
            self.load_sequence(application_elt, 'start_sequence', rules)
            self.load_sequence(application_elt, 'stop_sequence', rules)
            self.load_enum(application_elt, 'starting_strategy', StartingStrategies, rules)
            self.load_enum(application_elt, 'starting_failure_strategy', StartingFailureStrategies, rules)
            self.load_enum(application_elt, 'running_failure_strategy', RunningFailureStrategies, rules)
            self.logger.debug(f'Parser.load_application_rules: application {application_name} - rules {rules}')
        # check that rules are compliant with dependencies
        rules.check_dependencies(application_name)
        self.logger.debug(f'Parser.load_application_rules: application={application_name} rules={rules}')

    def get_application_element(self, application_name: str) -> Optional[Any]:
        """ Try to find the definition of an application in rules files.
        First try to find the definition based on the exact application name.
        If not found, second try to find a corresponding pattern.

        :param application_name: the application name
        :return: the XML element containing rules definition for an application
        """
        # try to find application name in rule files
        application_elt = None
        for root in self.roots:
            application_elt = root.find('./application[@name="{}"]'.format(application_name))
            # stop search on first element found
            if application_elt is not None:
                break
        self.logger.trace(f'Parser.get_application_element: direct search for application={application_name}'
                          f' found={application_elt is not None}')
        if application_elt is None:
            # if not found as it is, try to find a corresponding pattern
            pattern = self.get_best_pattern(application_name, self.application_patterns)
            application_elt = self.application_patterns.get(pattern)
        return application_elt

    def load_program_rules(self, namespec: str, rules: ProcessRules) -> None:
        """ Find an entry corresponding to the process in the rules, then load the parameters found.
        A final check is performed to detect inconsistencies.

        :param namespec: the process namespec
        :param rules: the process rules to fill
        :return: None
        """
        self.logger.trace(f'Parser.load_program_rules: searching program element for {namespec}')
        program_elt, is_pattern = self.get_program_element(namespec)
        if program_elt is not None:
            # load element parameters into rules
            self.load_model_rules(program_elt, rules, Parser.LOOP_CHECK)
        # check that rules are compliant with dependencies
        rules.check_dependencies(namespec, is_pattern)
        self.logger.debug(f'Parser.load_program_rules: process={namespec} is_pattern={is_pattern} rules=[{rules}]')

    def load_model_rules(self, program_elt: Any, rules: ProcessRules, loop_check: int) -> None:
        """ Load the parameters found whatever it is given by a program or a model section.
        If the section includes a reference to a model, it is loaded first and then eventually superseded
        by other attributes.

        :param program_elt: the XML element containing rules definition
        :param rules: the process structure used to store the rules found
        :param loop_check: the counter used to check the maximum number of recursive model references
        :return: None
        """
        # check if recursive depth has been reached
        if loop_check == 0:
            self.logger.warn(f'Parser.load_model_rules: Maximum number {Parser.LOOP_CHECK} of references reached')
            return
        # find check if a model is referenced in the program rules
        model_elt = self.get_model_element(program_elt)
        if model_elt is not None:
            self.logger.trace(f'Parser.load_model_rules: found model={model_elt.get("name")}'
                              f' from program={Parser.get_element_name(program_elt)}')
            # a model can reference another model
            # WARN: recursive call, counter decreased
            self.load_model_rules(model_elt, rules, loop_check - 1)
        # other attributes found may be used to complete or supersede the possible model
        self.load_identifiers(program_elt, rules)
        self.load_sequence(program_elt, 'start_sequence', rules)
        self.load_sequence(program_elt, 'stop_sequence', rules)
        self.load_boolean(program_elt, 'required', rules)
        self.load_boolean(program_elt, 'wait_exit', rules)
        self.load_expected_loading(program_elt, rules)
        self.load_enum(program_elt, 'starting_failure_strategy', StartingFailureStrategies, rules)
        self.load_enum(program_elt, 'running_failure_strategy', RunningFailureStrategies, rules)

    @staticmethod
    def get_element_name(elt: Any):
        """ Return the name or the pattern name of the element.

        :param elt: the application or program element
        :return: the name or pattern name attribute of the element
        """
        return elt.get('name') or elt.get('pattern')

    def get_program_element(self, namespec: str) -> Tuple[Optional[Any], bool]:
        """ Try to find the definition of a program in rules files.
        First try to find the definition based on the exact program name.
        If not found, second try to find a corresponding pattern.

        :param namespec: the process namespec
        :return: the XML element containing rules definition for a program
        """
        application_name, process_name = split_namespec(namespec)
        # try to find program name in file
        application_elt = self.get_application_element(application_name)
        if application_elt is None:
            self.logger.debug(f'Parser.get_program_element: no application element found for program={namespec}')
            return None, False
        program_elt = application_elt.find(f'./programs/program[@name="{process_name}"]')
        self.logger.trace(f'Parser.get_program_element: direct search for program={namespec} found'
                          f' {program_elt is not None}')
        is_pattern = False
        if program_elt is None:
            # if not found as it is, try to find a corresponding pattern
            if application_elt in self.program_patterns:
                prg_patterns = self.program_patterns[application_elt]
                pattern = self.get_best_pattern(process_name, prg_patterns.keys())
                program_elt = prg_patterns.get(pattern)
                is_pattern = program_elt is not None
        return program_elt, is_pattern

    def get_best_pattern(self, name: str, patterns: Dict) -> Optional[Any]:
        """ Return the pattern having the greatest capture for the string considered.

        :param name: the string to match
        :param patterns: the applicable patterns
        :return: the best pattern that matches the string
        """
        matching_patterns = []
        for pattern in patterns:
            # use a matching capture to get the regex performance
            mo = re.search(f'({pattern})', name)
            if mo:
                matching_patterns.append((pattern, mo.group()))
        self.logger.trace(f'Parser.get_best_pattern: found patterns={patterns} for {name}')
        if matching_patterns:
            # the best pattern is the one having the greatest capture
            pattern, performance = max(matching_patterns, key=lambda x: len(x[1]))
            self.logger.debug(f'Parser.get_best_pattern: pattern={pattern} (perf={performance}) selected for {name}')
            return pattern
        return None

    def get_model_element(self, elt: Any) -> Optional[Any]:
        """ Find if element references a model

        :param elt: the XML element containing rules definition for a program
        :return: the XML element containing rules definition for a model
        """
        model = elt.findtext('reference')
        return self.models.get(model, None)

    def check_identifier_list(self, identifier_list: str):
        """ Resolve and check the list of identifiers provided.

        :param identifier_list: the identifiers of the Supervisor instances, separated by commas
        :return: the list of validated identifiers
        """
        # get ordered list, removing duplicates and empty elements
        identifiers = list_of_strings(identifier_list)
        # resolve aliases by using list slicing to insert aliases
        # here an alias can be referenced in another alias if declared after in the XML
        for alias_name, alias in self.aliases.items():
            if alias_name in identifiers:
                pos = identifiers.index(alias_name)
                identifiers[pos:pos+1] = alias
        # WARN: checking the list vs the instances registered in supvisors_mapper has been removed
        #       so that
        # return ordered list, removing duplicates and empty elements
        return list(OrderedDict.fromkeys(filter(None, identifiers)))

    def load_identifiers(self, elt: Any, rules: AnyRules) -> None:
        """ Get the identifiers of the Supvisors instances where the program is allowed to run.

        :param elt: the XML element containing rules definition for a program
        :param rules: the process structure used to store the rules found
        :return: None
        """
        value = elt.findtext('identifiers')
        if value:
            identifiers = self.check_identifier_list(value)
            self.logger.trace(f'Parser.load_identifiers: value={value} identifiers={identifiers}')
            # clear the list from special signs but keep the information
            has_atsign = ATSIGN in identifiers
            has_hashtag = HASHTAG in identifiers
            for sign in [ATSIGN, HASHTAG]:
                if sign in identifiers:
                    identifiers.remove(sign)
            # if '*' is set, any other identifier is redundant
            # if '@' or '#' are set without any other identifier, all instances are applicable
            # if both '@' or '#' are set, '@' will prevail
            if ((has_atsign or has_hashtag) and not identifiers) or (WILDCARD in identifiers):
                identifiers = [WILDCARD]
            if has_atsign:
                # process cannot be started anywhere until at_identifiers are resolved
                rules.at_identifiers, rules.identifiers = identifiers, []
            if has_hashtag:
                # process cannot be started anywhere until hash_identifiers are resolved
                rules.hash_identifiers, rules.identifiers = identifiers, []
            # standard case
            if not has_atsign and not has_hashtag:
                rules.identifiers = identifiers
            self.logger.trace(f'Parser.load_identifiers: identifiers={rules.identifiers}'
                              f' at_identifiers={rules.at_identifiers} hash_identifiers={rules.hash_identifiers}')

    def load_sequence(self, elt: Any, attr_string: str, rules: AnyRules) -> None:
        """ Return the sequence value found from the XML element.
        The value must be greater than or equal to 0.

        :param elt: the XML element containing rules definition for an application or a program
        :param attr_string: the XML tag searched and the name of the rule attribute
        :param rules: the structure used to store the rules found
        :return: None
        """
        str_value = elt.findtext(attr_string)
        if str_value:
            try:
                value = int(str_value)
                if value >= 0:
                    setattr(rules, attr_string, value)
                else:
                    self.logger.error(f'Parser.load_sequence: invalid value for elt={Parser.get_element_name(elt)}'
                                      f' {attr_string}: {value} (expected integer >= 0)')
            except (TypeError, ValueError):
                self.logger.error(f'Parser.load_sequence: not an integer for elt={Parser.get_element_name(elt)}'
                                  f' {attr_string}: {str_value}')

    def load_expected_loading(self, elt: Any, rules: ProcessRules) -> None:
        """ Return the expected_loading value found from the XML element.
        The value must be in [0 ; 100].

        :param elt: the XML element containing rules definition for an application or a program
        :param rules: the structure used to store the rules found
        :return: None
        """
        str_value = elt.findtext('expected_loading')
        if str_value:
            try:
                value = int(str_value)
                if 0 <= value <= 100:
                    setattr(rules, 'expected_load', value)
                else:
                    self.logger.warn(f'Parser.load_expected_loading: invalid value for {Parser.get_element_name(elt)}'
                                     f' expected_loading: {value} (expected integer in [0;100])')
            except (TypeError, ValueError):
                self.logger.warn(f'Parser.load_expected_loading: not an integer for {Parser.get_element_name(elt)}'
                                 f' expected_loading: {str_value}')

    def load_boolean(self, elt: Any, attr_string: str, rules: AnyRules) -> None:
        """ Return the boolean value found from XML element.

        :param elt: the XML element containing rules definition for an application or a program
        :param attr_string: the XML tag searched and the name of the rule attribute
        :param rules: the structure used to store the rules found
        :return: None
        """
        str_value = elt.findtext(attr_string)
        if str_value:
            try:
                value = bool(strtobool(str_value))
                setattr(rules, attr_string, value)
            except ValueError:
                self.logger.warn(f'Parser.load_boolean: not a boolean-like for {Parser.get_element_name(elt)}'
                                 f' {attr_string}: {str_value}')

    def load_enum(self, elt: Any, attr_string: str, klass: EnumClassType, rules: AnyRules) -> None:
        """ Return the running_failure_strategy value found from XML element.
        The value MUST correspond to an enumeration value of RunningFailureStrategies.

        :param elt: the XML element containing rules definition for an application
        :param attr_string: the XML tag searched and the name of the rule attribute
        :param klass: the enum class to match
        :param rules: the application structure used to store the rules found
        :return: None
        """
        value = elt.findtext(attr_string)
        if value:
            try:
                setattr(rules, attr_string, klass[value])
            except KeyError:
                self.logger.warn(f'Pattern.load_enum: invalid value for {Parser.get_element_name(elt)}'
                                 f' {attr_string}: {value} (expected in {[x.name for x in klass]})')

    def parse(self, filename: str) -> Optional[Any]:
        """ Parse the file depending on the modules installed.
        lxml is considered first as it allows to check the XML through a schema.
        Elementtree is used as an alternative if lxml module cannot be imported.

        :param filename: the path of the XML rules file
        :return: the XML parser
        """
        # find parser
        self.logger.debug('Parser.parse: trying to use lxml.etree parser')
        try:
            from lxml.etree import parse, XMLSchema
            # parse XML and validate it
            tree = parse(filename)
            # get XSD
            schema_doc = parse(rules_xsd)
            schema = XMLSchema(schema_doc)
            if schema.validate(tree):
                self.logger.debug('Parser.parse: XML validated')
                return tree
            print(schema.error_log, file=stderr)
            raise ValueError(f'Parser.parse: XML NOT validated: {filename}')
        except ImportError:
            self.logger.debug('Parser.parse: failed to import lxml')
            self.logger.debug('Parser.parse: trying to use xml.etree.ElementTree parser')
            try:
                from xml.etree.ElementTree import parse
                return parse(filename)
            except ImportError:
                self.logger.critical('Parser.parse: failed to import ElementTree')
                raise
