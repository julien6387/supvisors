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

from typing import Sequence

from supvisors.address import *
from supvisors.application import ApplicationStatus
from supvisors.process import *
from supvisors.ttypes import AddressStates
from supvisors.utils import supvisors_shortcuts


class Context(object):
    """ The Context class holds the main data of Supvisors:
    - addresses: the dictionary of all AddressStatus (key is address),
    - forced_addresses: the dictionary of the minimal set of AddressStatus (key is address),
    - applications: the dictionary of all ApplicationStatus (key is application name),
    - processes: the dictionary of all ProcessStatus (key is process namespec),
    - master_address: the address of the Supvisors master,
    - master: a boolean telling if the local address is the master address.
    - new: a boolean telling if this context has just been started.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        # shortcuts for readability
        supvisors_shortcuts(self, ['address_mapper', 'info_source', 'logger', 'options'])
        # attributes
        self.addresses = {address_name: AddressStatus(address_name, self.logger)
                          for address_name in self.address_mapper.addresses}
        self.forced_addresses = {address_name: status
                                 for address_name, status in self.addresses.items()
                                 if address_name in self.options.force_synchro_if}
        self.applications = {}
        self.processes = {}
        self._master_address = ''
        self.master = False

    @property
    def master_address(self):
        """ Property for the 'master_address' attribute.
        The setter sets the 'master' attribute to True if the master address is the local address. """
        return self._master_address

    @master_address.setter
    def master_address(self, address):
        self.logger.info('Context.master_address: {}'.format(address))
        self._master_address = address
        self.master = address == self.address_mapper.local_address

    # methods on addresses
    def unknown_addresses(self):
        """ Return the AddressStatus instances in UNKNOWN state. """
        return self.addresses_by_states([AddressStates.UNKNOWN])

    def unknown_forced_addresses(self):
        """ Return the AddressStatus instances in UNKNOWN state. """
        return [status.address_name
                for status in self.forced_addresses.values()
                if status.state == AddressStates.UNKNOWN]

    def running_addresses(self):
        """ Return the AddressStatus instances in RUNNING state. """
        return self.addresses_by_states([AddressStates.RUNNING])

    def isolating_addresses(self):
        """ Return the AddressStatus instances in ISOLATING state. """
        return self.addresses_by_states([AddressStates.ISOLATING])

    def isolation_addresses(self):
        """ Return the AddressStatus instances in ISOLATING or ISOLATED
        state. """
        return self.addresses_by_states([AddressStates.ISOLATING, AddressStates.ISOLATED])

    def addresses_by_states(self, states):
        """ Return the AddressStatus instances sorted by state. """
        return [status.address_name
                for status in self.addresses.values()
                if status.state in states]

    def invalid(self, status):
        """ Declare SILENT or ISOLATING the AddressStatus in parameter, according to the auto_fence option.
        A local address is never ISOLATING, whatever the option is set or not.
        Give it a chance to restart. """
        if self.supvisors.options.auto_fence and status.address_name != self.address_mapper.local_address:
            status.state = AddressStates.ISOLATING
        else:
            status.state = AddressStates.SILENT
        # invalidate address in concerned processes
        # if local Supvisors is master, failure handler will be notified for processes running on this address
        for process in status.running_processes():
            process.invalidate_address(status.address_name, self.master)

    def end_synchro(self) -> None:
        """ Declare as SILENT the nodes that are still not responsive at the end of the INITIALIZATION state.

        :return: None
        """
        # consider problem if no tick received at the end of synchro time
        for address in self.addresses.values():
            if address.state == AddressStates.UNKNOWN:
                self.invalid(address)

    # methods on applications / processes
    def conflicting(self):
        """ Return True if any conflicting ProcessStatus is detected. """
        return next((True for process in self.processes.values()
                     if process.conflicting()), False)

    def conflicts(self):
        """ Return all conflicting ProcessStatus. """
        return [process for process in self.processes.values()
                if process.conflicting()]

    def setdefault_application(self, application_name):
        """ Return the application corresponding to application_name if found.
        Otherwise return a new application for application_name.
        Related application rules are loaded from the rules file. """
        try:
            # find existing application
            application = self.applications[application_name]
        except KeyError:
            # create new instance
            application = ApplicationStatus(application_name, self.logger)
            # load rules from rules file
            if self.supvisors.parser:
                self.supvisors.parser.load_application_rules(application)
            # add new application to context
            self.applications[application_name] = application
        return application

    def setdefault_process(self, info):
        """ Return the process corresponding to info if found.
        Otherwise return a new process for group name and process name.
        Related process rules are loaded from the rules file. """
        application_name = info['group']
        namespec = make_namespec(application_name, info['name'])
        try:
            # find existing process
            process = self.processes[namespec]
        except KeyError:
            # create new instance
            process = ProcessStatus(application_name, info['name'], self.supvisors)
            # apply default running failure strategy
            application = self.setdefault_application(process.application_name)
            process.rules.running_failure_strategy = application.rules.running_failure_strategy
            # load rules from rules file
            if self.supvisors.parser:
                self.supvisors.parser.load_process_rules(process)
            # add new process to context
            application.add_process(process)
            self.processes[namespec] = process
        return process

    def load_processes(self, address, all_info):
        """ Load application dictionary from process info got from Supervisor on address. """
        # get AddressStatus corresponding to address
        status = self.addresses[address]
        # store processes into their application entry
        for info in all_info:
            # get or create process
            process = self.setdefault_process(info)
            # update the current entry
            process.add_info(address, info)
            # share the instance to the Supervisor instance that holds it
            status.add_process(process)

    # methods on events
    def on_authorization(self, address_name: str, authorized: bool) -> Optional[bool]:
        """ Method called upon reception of an authorization event telling if the remote Supvisors instance
        authorizes the local Supvisors instance to process its events.

        :param address_name: the node name from which comes the event
        :param authorized: the node authorization status
        :return: True if authorized both ways
        """
        if self.address_mapper.valid(address_name):
            status = self.addresses[address_name]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                if authorized:
                    self.logger.info('Context.on_authorization: local is authorized to deal with {}'
                                     .format(address_name))
                    status.state = AddressStates.RUNNING
                    return True
                self.logger.warn('Context.on_authorization: local is not authorized to deal with {}'
                                 .format(address_name))
                self.invalid(status)
        else:
            self.logger.warn('Context.on_authorization: got authorization from unexpected location={}'
                             .format(address_name))

    def on_tick_event(self, address_name, event):
        """ Method called upon reception of a tick event from the remote Supvisors instance, telling that it is active.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method also updates the times of the corresponding AddressStatus and the ProcessStatus depending on it.
        Finally, the updated AddressStatus is published. """
        if self.address_mapper.valid(address_name):
            status = self.addresses[address_name]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                self.logger.debug('Context.on_tick_event: got tick {} from location={}'.format(event, address_name))
                # asynchronous port-knocking used to check if remote Supvisors instance considers
                # the local instance as isolated
                if status.state in [AddressStates.UNKNOWN, AddressStates.SILENT]:
                    status.state = AddressStates.CHECKING
                    self.supvisors.zmq.pusher.send_check_address(address_name)
                # update internal times
                status.update_times(event['when'], int(time()))
                # publish AddressStatus event
                self.supvisors.zmq.publisher.send_address_status(status.serial())
        else:
            self.logger.warn('Context.on_tick_event: got tick from unexpected location={}'.format(address_name))

    def on_process_event(self, address_name, event):
        """ Method called upon reception of a process event from the remote Supvisors instance.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method updates the ProcessStatus corresponding to the event, and thus the wrapping ApplicationStatus.
        Finally, the updated ProcessStatus and ApplicationStatus are published.
        """
        if self.address_mapper.valid(address_name):
            status = self.addresses[address_name]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                self.logger.debug('Context.on_process_event: got event {} from location={}'.format(event, address_name))
                try:
                    # get internal data
                    application = self.applications[event['group']]
                    process = application.processes[event['name']]
                    # update command line
                    self.info_source.update_extra_args(process.namespec(), event['extra_args'])
                except KeyError:
                    # process not found. normal when no tick yet received
                    # from this address
                    self.logger.debug('Context.on_process_event: reject event {} from location={}'
                                      .format(event, address_name))
                else:
                    # refresh process info from process event
                    process.update_info(address_name, event)
                    # refresh application status
                    application = self.applications[process.application_name]
                    application.update_status()
                    # publish process event, status and application status
                    publisher = self.supvisors.zmq.publisher
                    publisher.send_process_event(address_name, event)
                    publisher.send_process_status(process.serial())
                    publisher.send_application_status(application.serial())
                    return process
        else:
            self.logger.error('Context.on_process_event: got process event from unexpected location={}'
                .format(address_name))

    def on_timer_event(self):
        """ Check that all Supvisors instances are still publishing.
        Supvisors considers that there a Supvisors instance is not active if no tick received in last 10s. """
        for status in self.addresses.values():
            if status.state == AddressStates.RUNNING and (time() - status.local_time) > 10:
                self.invalid(status)
                # publish AddressStatus event
                self.supvisors.zmq.publisher.send_address_status(status.serial())

    def handle_isolation(self) -> Sequence[str]:
        """ Move ISOLATING addresses to ISOLATED and publish related events. """
        addresses = self.isolating_addresses()
        for address in addresses:
            status = self.addresses[address]
            status.state = AddressStates.ISOLATED
            # publish AddressStatus event
            self.supvisors.zmq.publisher.send_address_status(status.serial())
        return addresses
