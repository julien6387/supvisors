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

from collections import OrderedDict
from distutils.util import strtobool
from io import StringIO
from sys import stderr
from typing import Any, Optional, Union

from supervisor.datatypes import list_of_strings

from supvisors.application import ApplicationStatus, ApplicationRules
from supvisors.process import ProcessStatus, ProcessRules
from supvisors.ttypes import StartingFailureStrategies, RunningFailureStrategies
from supvisors.utils import supvisors_shortcuts

# XSD contents for XML validation
XSDContents = StringIO('''\
<xs:schema attributeFormDefault="unqualified" elementFormDefault="qualified"
xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:simpleType name="Loading">
        <xs:restriction base="xs:int">
            <xs:minInclusive value="0"/>
            <xs:maxInclusive value="100"/>
        </xs:restriction>
    </xs:simpleType>
    <xs:simpleType name="StartingFailureStrategy" final="restriction" >
        <xs:restriction base="xs:string">
            <xs:enumeration value="ABORT" />
            <xs:enumeration value="CONTINUE" />
            <xs:enumeration value="STOP" />
        </xs:restriction>
    </xs:simpleType>
    <xs:simpleType name="RunningFailureStrategy" final="restriction" >
        <xs:restriction base="xs:string">
            <xs:enumeration value="CONTINUE" />
            <xs:enumeration value="RESTART_PROCESS" />
            <xs:enumeration value="STOP_APPLICATION" />
            <xs:enumeration value="RESTART_APPLICATION" />
        </xs:restriction>
    </xs:simpleType>
    <xs:complexType name="ProgramModel">
        <xs:sequence>
            <xs:element type="xs:string" name="reference" minOccurs="0" maxOccurs="1"/>
            <xs:element type="xs:string" name="addresses" minOccurs="0" maxOccurs="1"/>
            <xs:element type="xs:byte" name="start_sequence" minOccurs="0" maxOccurs="1"/>
            <xs:element type="xs:byte" name="stop_sequence" minOccurs="0" maxOccurs="1"/>
            <xs:element type="xs:boolean" name="required" minOccurs="0" maxOccurs="1"/>
            <xs:element type="xs:boolean" name="wait_exit" minOccurs="0" maxOccurs="1"/>
            <xs:element type="Loading" name="expected_loading" minOccurs="0" maxOccurs="1"/>
            <xs:element type="RunningFailureStrategy" name="running_failure_strategy" minOccurs="0" maxOccurs="1"/>
        </xs:sequence>
        <xs:attribute type="xs:string" name="name" use="required"/>
    </xs:complexType>
    <xs:complexType name="ApplicationModel">
        <xs:sequence>
            <xs:element type="xs:byte" name="start_sequence" minOccurs="0" maxOccurs="1"/>
            <xs:element type="xs:byte" name="stop_sequence" minOccurs="0" maxOccurs="1"/>
            <xs:element type="StartingFailureStrategy" name="starting_failure_strategy" minOccurs="0" maxOccurs="1"/>
            <xs:element type="RunningFailureStrategy" name="running_failure_strategy" minOccurs="0" maxOccurs="1"/>
            <xs:choice minOccurs="0" maxOccurs="unbounded">
                <xs:element type="ProgramModel" name="program"/>
                <xs:element type="ProgramModel" name="pattern"/>
            </xs:choice>
        </xs:sequence>
        <xs:attribute type="xs:string" name="name" use="required"/>
    </xs:complexType>
    <xs:element name="root">
        <xs:complexType>
            <xs:sequence>
                <xs:choice minOccurs="0" maxOccurs="unbounded">
                    <xs:element type="ProgramModel" name="model"/>
                    <xs:element type="ApplicationModel" name="application"/>
                </xs:choice>
            </xs:sequence>
        </xs:complexType>
    </xs:element>
</xs:schema>
''')


class Parser(object):
    """ The Parser class used to get application and program rules from an XML file. """

    # for recursive references to program models, depth is limited to 3
    LOOP_CHECK = 3

    def __init__(self, supvisors: Any) -> None:
        """ The constructor parses the XML file and stores references to models and patterns found.

        :param supvisors: the global Supvisors structure.
        """
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['logger'])
        self.tree = self.parse(supvisors.options.rules_file)
        self.root = self.tree.getroot()
        # get models
        elements = self.root.findall("./model[@name]")
        self.models = {element.get('name'): element for element in elements}
        self.logger.debug('Parser.__init__: found models {}'.format(self.models.keys()))
        # get patterns
        elements = self.root.findall(".//pattern[@name]")
        self.patterns = {element.get('name'): element for element in elements}
        self.logger.debug('Parser.__init__: found patterns {}'.format(self.patterns.keys()))

    def load_application_rules(self, application: ApplicationStatus) -> None:
        """ Find an entry corresponding to the application in the rules file, then load the parameters found.

        :param application: the application for which to find rules in the XML rules file
        :return: None
        """
        # find application element using an xpath
        self.logger.trace('Parser.load_application_rules: searching application element for {}'
                          .format(application.application_name))
        application_elt = self.root.find('./application[@name="{}"]'.format(application.application_name))
        if application_elt is not None:
            rules = application.rules
            self.load_sequence(application_elt, 'start_sequence', rules)
            self.load_sequence(application_elt, 'stop_sequence', rules)
            self.load_enum(application_elt, 'starting_failure_strategy', StartingFailureStrategies, rules)
            self.load_enum(application_elt, 'running_failure_strategy', RunningFailureStrategies, rules)
            self.logger.debug('Parser.load_application_rules: application {} - rules {}'
                              .format(application.application_name, rules))

    def load_process_rules(self, process: ProcessStatus) -> None:
        """ Find an entry corresponding to the process in the rules, then load the parameters found.
        A final check is performed to detect inconsistencies.

        :param process: the process for which to find rules in the XML rules file
        :return: None
        """
        self.logger.trace('Parser.load_process_rules: searching program element for {}'
                          .format(process.namespec()))
        program_elt = self.get_program_element(process)
        if program_elt is not None:
            # load element parameters into rules
            self.load_model_rules(program_elt, process.rules, Parser.LOOP_CHECK)
            # check that rules are compliant with dependencies
            process.rules.check_dependencies(process.namespec())
            self.logger.debug('Parser.load_process_rules: process {} - rules {}'
                              .format(process.namespec(), process.rules))

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
            self.logger.trace('Parser.load_model_rules: found model {} from program {}'
                              .format(model_elt.get('name'), program_elt.get('name')))
            # a model can reference another model
            # WARN: recursive call, counter decreased
            self.load_model_rules(model_elt, rules, loop_check - 1)
        # other attributes found may be used to complete or supersede the possible model
        self.load_program_addresses(program_elt, rules)
        self.load_sequence(program_elt, 'start_sequence', rules)
        self.load_sequence(program_elt, 'stop_sequence', rules)
        self.load_boolean(program_elt, 'required', rules)
        self.load_boolean(program_elt, 'wait_exit', rules)
        self.load_loading(program_elt, rules)
        self.load_enum(program_elt, 'running_failure_strategy', RunningFailureStrategies, rules)

    def get_program_element(self, process: ProcessStatus) -> Optional[Any]:
        """ Try to find the definition of a program in rules files.
        First try to to find the definition based on the exact program name.
        If not found, second try to find a corresponding pattern.

        :param process: the process for which to find rules in the XML rules file
        :return: the XML element containing rules definition for a program
        """
        # try to find program name in file
        program_elt = self.root.find('./application[@name="{}"]/program[@name="{}"]'
                                     .format(process.application_name, process.process_name))
        self.logger.trace('Parser.get_program_element: direct search for program {} found={}'
                          .format(process.namespec(), program_elt is not None))
        if program_elt is None:
            # if not found as it is, try to find a corresponding pattern
            patterns = [name for name, element in self.patterns.items() if name in process.namespec()]
            self.supvisors.logger.trace('Parser.get_program_element: found patterns {} for program {}'
                                        .format(patterns, process.namespec()))
            if patterns:
                pattern = max(patterns, key=len)
                program_elt = self.patterns[pattern]
                self.logger.trace('Parser.get_program_element: pattern {} chosen for program {}'
                                  .format(pattern, process.namespec()))
        return program_elt

    def get_model_element(self, elt: Any) -> Optional[Any]:
        """ Find if element references a model

        :param elt: the XML element containing rules definition for a program
        :return: the XML element containing rules definition for a model
        """
        model = elt.findtext('reference')
        return self.models.get(model, None)

    def load_program_addresses(self, elt: Any, rules: ProcessRules) -> None:
        """ Get the addresses where the program is authorized to run.

        :param elt: the XML element containing rules definition for a program
        :param rules: the process structure used to store the rules found
        :return: None
        """
        value = elt.findtext('addresses')
        if value:
            # sort and trim list of values
            addresses = list(OrderedDict.fromkeys(filter(None, list_of_strings(value))))
            if '#' in addresses:
                # process cannot be started anywhere until hash address is resolved
                rules.addresses = []
                # if '#' is alone or associated to '*', the logic is applicable to all addresses
                if len(addresses) == 1 or '*' in addresses:
                    rules.hash_addresses = ['*']
                else:
                    # '#' is applicable to a subset of addresses
                    addresses.remove('#')
                    rules.hash_addresses = addresses
            elif '*' in addresses:
                rules.addresses = ['*']
            else:
                rules.addresses = self.supvisors.address_mapper.filter(addresses)

    def load_sequence(self, elt: Any, attr_string: str, rules: Union[ApplicationRules, ProcessRules]) -> None:
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
                    self.logger.warn('Parser.load_sequence: invalid value for {} {}: {} (expected integer >= 0)'
                                     .format(elt.get('name'), attr_string, value))
            except (TypeError, ValueError):
                self.logger.warn('Parser.load_sequence: not an integer for {} {}: {}'
                                 .format(elt.get('name'), attr_string, str_value))

    def load_loading(self, elt: Any, rules: ProcessRules) -> None:
        """ Return the loading value found from the XML element.
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
                    setattr(rules, 'expected_loading', value)
                else:
                    self.logger.warn('Parser.load_sequence: invalid value for {} expected_loading: {}'
                                     '(expected integer in [0;100])'.format(elt.get('name'), value))
            except (TypeError, ValueError):
                self.logger.warn('Parser.load_sequence: not an integer for {} expected_loading: {}'
                                 .format(elt.get('name'), str_value))

    def load_boolean(self, elt: Any, attr_string: str, rules: ProcessRules) -> None:
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
                self.logger.warn('Parser.load_boolean: not a boolean-like for {} {}: {}'
                                 .format(elt.get('name'), attr_string, str_value))

    def load_enum(self, elt: Any, attr_string: str, klass, rules: Union[ApplicationRules, ProcessRules]) -> None:
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
                setattr(rules, attr_string, klass.from_string(value))
            except KeyError:
                self.logger.warn('Pattern.load_enum: invalid value for {} {}: {} (expected in {})'
                                 .format(elt.get('name'), attr_string, value, klass.strings()))

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
            schema_doc = parse(XSDContents)
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
