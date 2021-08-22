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

from distutils.util import strtobool
from os import path
from sys import stderr
from typing import Any, Dict, List, Optional, Union

from supervisor.datatypes import list_of_strings
from supervisor.options import split_namespec

from .application import ApplicationRules
from .process import ProcessRules
from .ttypes import StartingStrategies, StartingFailureStrategies, RunningFailureStrategies, EnumClassType

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
        """ The constructor parses the XML file and stores references to models and patterns found.

        :param supvisors: the global Supvisors structure.
        """
        self.supvisors = supvisors
        self.logger = supvisors.logger
        self.tree = self.parse(supvisors.options.rules_file)
        self.root = self.tree.getroot()
        # get aliases - check nodes and back to string as it is easier to process
        self.aliases = {element.get('name'): list_of_strings(element.text)
                        for element in self.root.findall("./alias[@name]")
                        if element.text}
        self.logger.debug('Parser: found aliases {}'.format(self.aliases))
        # get models
        elements = self.root.findall("./model[@name]")
        self.models = {element.get('name'): element for element in elements}
        self.logger.debug('Parser: found models {}'.format(self.models.keys()))
        # get application patterns
        app_elements = self.root.findall(".//application[@pattern]")
        self.application_patterns = {app_element.get('pattern'): app_element for app_element in app_elements}
        self.logger.debug('Parser: found application patterns {}'.format(self.application_patterns.keys()))
        # get program patterns
        self.program_patterns = {}
        app_elements = self.root.findall(".//application/pattern[@name]/..")
        for app_element in app_elements:
            prg_elements = app_element.findall("./pattern[@name]")
            self.program_patterns[app_element] = {prg_element.get('name'): prg_element for prg_element in prg_elements}
        if self.program_patterns:
            self.logger.warn('Parser: usage of pattern elements is deprecated -'
                             ' please convert {} to program elements with pattern attribute.'
                             .format(self.printable_program_patterns()))
        app_elements = self.root.findall(".//application/program[@pattern]/..")
        for app_element in app_elements:
            prg_elements = app_element.findall("./program[@pattern]")
            prg_patterns = self.program_patterns.setdefault(app_element, {})
            prg_patterns.update({prg_element.get('pattern'): prg_element for prg_element in prg_elements})
        self.logger.debug('Parser: found program patterns {}'.format(self.printable_program_patterns()))

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
        # find application element using an xpath
        self.logger.trace('Parser.load_application_rules: searching application element for {}'
                          .format(application_name))
        application_elt = self.get_application_element(application_name)
        if application_elt is not None:
            rules.managed = True
            self.load_boolean(application_elt, 'distributed', rules)
            self.load_application_nodes(application_elt, rules)
            self.load_sequence(application_elt, 'start_sequence', rules)
            self.load_sequence(application_elt, 'stop_sequence', rules)
            self.load_enum(application_elt, 'starting_strategy', StartingStrategies, rules)
            self.load_enum(application_elt, 'starting_failure_strategy', StartingFailureStrategies, rules)
            self.load_enum(application_elt, 'running_failure_strategy', RunningFailureStrategies, rules)
            self.logger.debug('Parser.load_application_rules: application {} - rules {}'
                              .format(application_name, rules))

    def get_application_element(self, application_name: str) -> Optional[Any]:
        """ Try to find the definition of an application in rules files.
        First try to to find the definition based on the exact application name.
        If not found, second try to find a corresponding pattern.

        :param application_name: the application name
        :return: the XML element containing rules definition for an application
        """
        # try to find program name in file
        application_elt = self.root.find('./application[@name="{}"]'.format(application_name))
        self.logger.trace('Parser.get_application_element: direct search for application={} found={}'
                          .format(application_name, application_elt is not None))
        if application_elt is None:
            # if not found as it is, try to find a corresponding pattern
            # TODO: use regexp ?
            patterns = [name for name, element in self.application_patterns.items() if name in application_name]
            self.logger.trace('Parser.get_application_element: found patterns={} for application={}'
                              .format(patterns, application_name))
            if patterns:
                pattern = max(patterns, key=len)
                application_elt = self.application_patterns[pattern]
                self.logger.trace('Parser.get_application_element: pattern={} chosen for application={}'
                                  .format(pattern, application_name))
        return application_elt

    def load_program_rules(self, namespec: str, rules: ProcessRules) -> None:
        """ Find an entry corresponding to the process in the rules, then load the parameters found.
        A final check is performed to detect inconsistencies.

        :param namespec: the process namespec
        :param rules: the process rules to fill
        :return: None
        """
        self.logger.trace('Parser.load_process_rules: searching program element for {}'.format(namespec))
        program_elt = self.get_program_element(namespec)
        if program_elt is not None:
            # load element parameters into rules
            self.load_model_rules(program_elt, rules, Parser.LOOP_CHECK)
            # check that rules are compliant with dependencies
            rules.check_dependencies(namespec)
            self.logger.debug('Parser.load_process_rules: process {} - rules {}'.format(namespec, rules))

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
            self.logger.warn('Parser.load_model_rules: Maximum number of model referencing reached: {} levels',
                             Parser.LOOP_CHECK)
            return
        # find check if a model is referenced in the program rules
        model_elt = self.get_model_element(program_elt)
        if model_elt is not None:
            self.logger.trace('Parser.load_model_rules: found model={} from program={}'
                              .format(model_elt.get('name'), Parser.get_element_name(program_elt)))
            # a model can reference another model
            # WARN: recursive call, counter decreased
            self.load_model_rules(model_elt, rules, loop_check - 1)
        # other attributes found may be used to complete or supersede the possible model
        self.load_program_nodes(program_elt, rules)
        self.load_sequence(program_elt, 'start_sequence', rules)
        self.load_sequence(program_elt, 'stop_sequence', rules)
        self.load_boolean(program_elt, 'required', rules)
        self.load_boolean(program_elt, 'wait_exit', rules)
        self.load_expected_loading(program_elt, rules)
        self.load_enum(program_elt, 'running_failure_strategy', RunningFailureStrategies, rules)

    @staticmethod
    def get_element_name(elt: Any):
        """ Return the name or the pattern name of the element.

        :param elt: the application or program element
        :return: the name or pattern name attribute of the element
        """
        return elt.get('name') or elt.get('pattern')

    def get_program_element(self, namespec: str) -> Optional[Any]:
        """ Try to find the definition of a program in rules files.
        First try to to find the definition based on the exact program name.
        If not found, second try to find a corresponding pattern.

        :param namespec: the process namespec
        :return: the XML element containing rules definition for a program
        """
        application_name, process_name = split_namespec(namespec)
        # try to find program name in file
        application_elt = self.get_application_element(application_name)
        if application_elt is None:
            self.logger.debug('Parser.get_program_element: no application element found for program={}'
                              .format(namespec))
            return None
        program_elt = application_elt.find('./program[@name="{}"]'.format(process_name))
        self.logger.trace('Parser.get_program_element: direct search for program={} found={}'
                          .format(namespec, program_elt is not None))
        if program_elt is None:
            # if not found as it is, try to find a corresponding pattern
            # TODO: use regexp ?
            if application_elt in self.program_patterns:
                prg_patterns = self.program_patterns[application_elt]
                patterns = [name for name in prg_patterns.keys() if name in process_name]
                self.logger.trace('Parser.get_program_element: found patterns={} for program={}'
                                  .format(patterns, namespec))
                if patterns:
                    pattern = max(patterns, key=len)
                    program_elt = prg_patterns[pattern]
                    self.logger.trace('Parser.get_program_element: pattern={} chosen for program={}'
                                      .format(pattern, namespec))
        return program_elt

    def get_model_element(self, elt: Any) -> Optional[Any]:
        """ Find if element references a model

        :param elt: the XML element containing rules definition for a program
        :return: the XML element containing rules definition for a model
        """
        model = elt.findtext('reference')
        return self.models.get(model, None)

    def check_node_list(self, str_node_list: str):
        """ Resolve and check the list of nodes provided.

        :param str_node_list: the node names, separated by commas
        :return: the list of validated nodes and of validated hash_nodes
        """
        # resolve aliases
        # Version 1: simple pass on input elements considering that an alias cannot include another alias
        # node_names = []
        # for node_name in list_of_strings(str_node_list):
        #     if node_name in self.aliases:
        #         node_names.extend(self.aliases[node_name])
        #     else:
        #         node_names.append(node_name)
        # Version 2: use list slicing to insert aliases
        # here an alias can be referenced in another alias if declared after in the XML
        node_names = list_of_strings(str_node_list)
        for alias_name, alias in self.aliases.items():
            if alias_name in node_names:
                pos = node_names.index(alias_name)
                node_names[pos:pos] = alias
        # keep reference to hashtag as it will be removed by the filters
        ref_hashtag = '#' in node_names
        if '*' in node_names:
            node_names = ['*']
        else:
            # filter the unknown nodes (or remaining aliases)
            node_names = self.supvisors.address_mapper.filter(node_names)
        # re-inject the hashtag if needed. position does not matter
        if ref_hashtag:
            node_names.append('#')
        return node_names

    def load_application_nodes(self, elt: Any, rules: ApplicationRules) -> None:
        """ Get the nodes where the non-distributed application is authorized to run.

        :param elt: the XML element containing rules definition for an application
        :param rules: the application structure used to store the rules found
        :return: None
        """
        value = elt.findtext('addresses')
        if value:
            rules.node_names = self.check_node_list(value)

    def load_program_nodes(self, elt: Any, rules: ProcessRules) -> None:
        """ Get the nodes where the program is authorized to run.

        :param elt: the XML element containing rules definition for a program
        :param rules: the process structure used to store the rules found
        :return: None
        """
        value = elt.findtext('addresses')
        if value:
            rules.node_names = self.check_node_list(value)
            if '#' in rules.node_names:
                # if '#' is alone or associated to '*', the logic is applicable to all addresses
                if len(rules.node_names) == 1 or '*' in rules.node_names:
                    rules.hash_node_names = ['*']
                else:
                    # '#' is applicable to a subset of node names
                    rules.node_names.remove('#')
                    rules.hash_node_names = rules.node_names
                # process cannot be started anywhere until hash node is resolved
                rules.node_names = []
            elif '*' in rules.node_names:
                rules.node_names = ['*']

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
                    self.logger.error('Parser.load_sequence: invalid value for elt={} {}: {} (expected integer >= 0)'
                                      .format(Parser.get_element_name(elt), attr_string, value))
            except (TypeError, ValueError):
                self.logger.error('Parser.load_sequence: not an integer for elt={} {}: {}'
                                  .format(Parser.get_element_name(elt), attr_string, str_value))

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
                    self.logger.warn('Parser.load_expected_loading: invalid value for elt={} expected_loading: {}'
                                     '(expected integer in [0;100])'.format(Parser.get_element_name(elt), value))
            except (TypeError, ValueError):
                self.logger.warn('Parser.load_expected_loading: not an integer for elt={} expected_loading: {}'
                                 .format(Parser.get_element_name(elt), str_value))

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
                self.logger.warn('Parser.load_boolean: not a boolean-like for elt={} {}: {}'
                                 .format(Parser.get_element_name(elt), attr_string, str_value))

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
                self.logger.warn('Pattern.load_enum: invalid value for elt={} {}: {} (expected in {})'
                                 .format(Parser.get_element_name(elt), attr_string, value, klass._member_names_))

    def parse(self, filename: str) -> Optional[Any]:
        """ Parse the file depending on the modules installed.
        lxml is considered first as it allows to check the XML through a schema.
        Elementtree is used as an alternative if lxml module cannot be imported.

        :param filename: the path of the XML rules file
        :return: the XML parser
        """
        # find parser
        self.logger.info('Parser.parse: trying to use lxml.etree parser')
        try:
            from lxml.etree import parse, XMLSchema
            # parse XML and validate it
            tree = parse(filename)
            # get XSD
            schema_doc = parse(rules_xsd)
            schema = XMLSchema(schema_doc)
            if schema.validate(tree):
                self.logger.info('Parser.parse: XML validated')
                return tree
            print(schema.error_log, file=stderr)
            raise ValueError('Parser.parse: XML NOT validated: {}'.format(filename))
        except ImportError:
            self.logger.info('Parser.parse: failed to import lxml')
            self.logger.info('Parser.parse: trying to use xml.etree.ElementTree parser')
            try:
                from xml.etree.ElementTree import parse
                return parse(filename)
            except ImportError:
                self.logger.critical('Parser.parse: failed to import ElementTree from any known place')
                raise
