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
from io import StringIO
from sys import stderr

from supervisor.datatypes import boolean, list_of_strings

from supvisors.ttypes import (StartingFailureStrategies,
                              RunningFailureStrategies)
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
        <xs:choice>
            <xs:element type="xs:string" name="reference"/>
            <xs:sequence>
                <xs:element type="xs:string" name="addresses" minOccurs="0" maxOccurs="1"/>
                <xs:element type="xs:byte" name="start_sequence" minOccurs="0" maxOccurs="1"/>
                <xs:element type="xs:byte" name="stop_sequence" minOccurs="0" maxOccurs="1"/>
                <xs:element type="xs:boolean" name="required" minOccurs="0" maxOccurs="1"/>
                <xs:element type="xs:boolean" name="wait_exit" minOccurs="0" maxOccurs="1"/>
                <xs:element type="Loading" name="expected_loading" minOccurs="0" maxOccurs="1"/>
                <xs:element type="RunningFailureStrategy" name="running_failure_strategy" minOccurs="0" maxOccurs="1"/>
            </xs:sequence>
        </xs:choice>
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

    def __init__(self, supvisors):
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['logger'])
        self.tree = self.parse(supvisors.options.rules_file)
        self.root = self.tree.getroot()
        # get models
        elements = self.root.findall("./model[@name]")
        self.models = {element.get('name'): element for element in elements}
        self.logger.debug(self.models)
        # get patterns
        elements = self.root.findall(".//pattern[@name]")
        self.patterns = {element.get('name'): element for element in elements}
        self.logger.debug(self.patterns)

    def load_application_rules(self, application):
        # find application element
        self.logger.trace('searching application element for {}'.format(application.application_name))
        application_elt = self.root.find("./application[@name='{}']".format(application.application_name))
        if application_elt is not None:
            # get start_sequence rule
            value = application_elt.findtext('start_sequence')
            application.rules.start_sequence = int(value) if value and int(value) > 0 else 0
            # get stop_sequence rule
            value = application_elt.findtext('stop_sequence')
            application.rules.stop_sequence = int(value) if value and int(value) > 0 else 0
            # get starting_failure_strategy rule
            value = application_elt.findtext('starting_failure_strategy')
            if value:
                strategy = StartingFailureStrategies.from_string(value)
                if strategy:
                    application.rules.starting_failure_strategy = strategy
            # get running_failure_strategy rule
            value = application_elt.findtext('running_failure_strategy')
            if value:
                strategy = RunningFailureStrategies.from_string(value)
                if strategy:
                    application.rules.running_failure_strategy = strategy
            # final print
            self.logger.debug('application {} - rules {}'.format(application.application_name, application.rules))

    def load_process_rules(self, process):
        self.logger.trace('searching program element for {}'.format(process.namespec()))
        program_elt = self.get_program_element(process)
        rules = process.rules
        if program_elt is not None:
            # get addresses rule
            self.get_program_addresses(program_elt, rules)
            # get start_sequence rule
            value = program_elt.findtext('start_sequence')
            try:
                rules.start_sequence = int(value)
                if rules.start_sequence < 0:
                    raise
            except:
                rules.start_sequence = 0
            # get stop_sequence rule
            value = program_elt.findtext('stop_sequence')
            try:
                rules.stop_sequence = int(value)
                if rules.stop_sequence < 0:
                    raise
            except:
                rules.stop_sequence = 0
            # get required rule
            value = program_elt.findtext('required')
            try:
                rules.required = boolean(value)
            except:
                rules.required = False
            # get wait_exit rule
            value = program_elt.findtext('wait_exit')
            try:
                rules.wait_exit = boolean(value)
            except:
                rules.wait_exit = False
            # get expected_loading rule
            value = program_elt.findtext('expected_loading')
            try:
                rules.expected_loading = int(value)
                if not 0 <= rules.expected_loading <= 100:
                    raise
            except:
                rules.expected_loading = 1
            # get running_failure_strategy rule
            value = program_elt.findtext('running_failure_strategy')
            if value:
                try:
                    strategy = RunningFailureStrategies.from_string(value)
                except KeyError:
                    self.logger.error('strategy {} unknown'.format(value))
                else:
                    rules.running_failure_strategy = strategy
            # check that rules are compliant with dependencies
            rules.check_dependencies(process.namespec())
            self.logger.debug('process {} - rules {}'.format(process.namespec(), rules))

    def get_program_addresses(self, program_elt, rules):
        value = program_elt.findtext('addresses')
        if value:
            # sort and trim
            addresses = list(OrderedDict.fromkeys(filter(None, list_of_strings(value))))
            if '*' in addresses:
                rules.addresses = ['*']
            elif '#' in addresses:
                rules.addresses = ['#']
            else:
                rules.addresses = self.supvisors.address_mapper.filter(addresses)

    def get_program_element(self, process):
        # try to find program name in file
        program_elt = self.root.find(
            "./application[@name='{}']/program[@name='{}']".format(process.application_name, process.process_name))
        self.logger.trace('{} - direct search program element {}'.format(process.namespec(), program_elt))
        if program_elt is None:
            # try to find a corresponding pattern
            patterns = [name for name, element in self.patterns.items() if name in process.namespec()]
            self.supvisors.logger.trace('{} - found patterns {}'.format(process.namespec(), patterns))
            if patterns:
                pattern = max(patterns, key=len)
                program_elt = self.patterns[pattern]
            self.logger.trace('{} - pattern search program element {}'.format(process.namespec(), program_elt))
        if program_elt is not None:
            # find if model referenced in element
            model = program_elt.findtext('reference')
            if model in self.models.keys():
                program_elt = self.models[model]
            self.logger.trace(
                '{} - model search ({}) program element {}'.format(process.namespec(), model, program_elt))
        return program_elt

    def parse(self, filename):
        """ Parse the file depending on the modules installed. """
        # find parser
        try:
            from lxml.etree import parse, XMLSchema
            self.logger.info('using lxml.etree parser')
            # parse XML and validate it
            tree = parse(filename)
            # get XSD
            schema_doc = parse(XSDContents)
            schema = XMLSchema(schema_doc)
            if schema.validate(tree):
                self.logger.info('XML validated')
                return tree
            print(schema.error_log, file=stderr)
            raise ValueError('XML NOT validated: {}'.format(filename))
        except ImportError:
            try:
                from xml.etree.ElementTree import parse
                self.logger.info('using xml.etree.ElementTree parser')
                return parse(filename)
            except ImportError:
                self.logger.critical("Failed to import ElementTree from any known place")
                raise
