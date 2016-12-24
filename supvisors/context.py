#!/usr/bin/python
#-*- coding: utf-8 -*-

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

from time import time

from supervisor.xmlrpc import RPCError

from supvisors.address import *
from supvisors.application import ApplicationStatus
from supvisors.process import *
from supvisors.utils import supvisors_short_cuts


class Context(object):
    """ The Context class holds the main data of Supvisors:
    - addresses: the dictionary of all AddressStatus (key is address),
    - applications: the dictionary of all ApplicationStatus (key is application name),
    - processes: the dictionary of all ProcessStatus (key is process namespec),
    - master_address: the address of the Supvisors master,
    - master: a boolean telling if the local address is the master address. """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        # shortcuts for readability
        supvisors_short_cuts(self, ['address_mapper', 'logger'])
        # attributes
        self.addresses = {address: AddressStatus(address, self.logger) for address in self.address_mapper.addresses}
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
        self._master_address = address
        self.master = address == self.address_mapper.local_address
 
    # methods on addresses
    def unknown_addresses(self):
        """ Return the AddressStatus instances in UNKNOWN state. """
        return self.addresses_by_states([AddressStates.UNKNOWN])

    def running_addresses(self):
        """ Return the AddressStatus instances in RUNNING state. """
        return self.addresses_by_states([AddressStates.RUNNING])

    def isolating_addresses(self):
        """ Return the AddressStatus instances in ISOLATING state. """
        return self.addresses_by_states([AddressStates.ISOLATING])

    def isolation_addresses(self):
        """ Return the AddressStatus instances in ISOLATING or ISOLATED state. """
        return self.addresses_by_states([AddressStates.ISOLATING, AddressStates.ISOLATED])

    def addresses_by_states(self, states):
        """ Return the AddressStatus instances sorted by state. """
        return [status.address_name for status in self.addresses.values() if status.state in states]

    def end_synchro(self):
        """ Declare as SILENT the AddressStatus that are still not responsive at the end of the INITIALIZATION state of Supvisors """
        # consider problem if no tick received at the end of synchro time
        map(self.invalid, filter(lambda x: x.state == AddressStates.UNKNOWN, self.addresses.values()))

    def invalid(self, status):
        """ Declare SILENT or ISOLATING the AddressStatus in parameter, according to the auto_fence option.
        A local address is never ISOLATING, whatever the option is set or not. Give it a chance to restart. """
        if self.supvisors.options.auto_fence and status.address_name != self.address_mapper.local_address:
            status.state = AddressStates.ISOLATING
        else:
            status.state = AddressStates.SILENT
        # invalidate address in concerned processes
        for process in status.running_processes():
            process.invalidate_address(status.address_name)

    # methods on applications / processes
    def process_from_info(self, info):
        """ Return the ProcessStatus instance corresponding to the ProcessInfo dictionary in parameter. """
        return self.get_process(info['group'], info['name'])

    def process_from_event(self, event):
        """ Return the ProcessStatus instance corresponding to the ProcessEvent dictionary in parameter. """
        return self.get_process(event['groupname'], event['processname'])

    def get_process(self, application_name, process_name):
        """ Return the ProcessStatus instance corresponding to the application and process names. """
        return self.applications[application_name].processes[process_name]

    def marked_processes(self):
        """ Return all the ProcessStatus instances having their mark_for_restart attribute set to True.
        This mark is used to restart:
        - a process that was running on a lost address,
        - a conflicting process, i.e. more than one instance of the same process is running on different addresses. """
        return [process for process in self.processes.values() if process.mark_for_restart]

    def conflicting(self):
        """ Return True if any conflicting ProcessStatus is detected. """
        return next((True for process in self.processes.values() if process.conflicting()), False)

    def conflicts(self):
        """ Return all conflicting ProcessStatus. """
        return [process for process in self.processes.values() if process.conflicting()]

    def load_processes(self, address, all_info):
        """ Load application dictionary from process info got from Supervisor on address. """
        # get all processes and sort them by group (application)
        # first store applications in a set
        application_list = {x['group'] for x  in all_info}
        self.logger.debug('applicationList={} from {}'.format(application_list, address))
        # add unknown applications
        for application_name in application_list:
            if application_name not in self.applications.keys():
                application = ApplicationStatus(application_name, self.logger)
                self.supvisors.parser.load_application_rules(application)
                self.applications[application_name] = application
        # get AddressStatus corresponding to address
        status = self.addresses[address]
        # store processes into their application entry
        for info in all_info:
            try:
                process = self.process_from_info(info)
            except KeyError:
                # not found. add new ProcessStatus instance to dictionary and application
                process = ProcessStatus(info['group'], info['name'], self.supvisors)
                self.supvisors.parser.load_process_rules(process)
                self.processes[process.namespec()] = process
                self.applications[process.application_name].add_process(process)
            # update the current entry
            process.add_info(address, info)
            # share the instance to the Supervisor instance that holds it
            status.add_process(process)

    # methods on events
    def check_address(self, status):
        """ Check that the local instance is allowed to deal with the remote instance if auto fencing is activated.
        If authorization is made or auto fencing is not set, information about the processes handled in the remote Supervisor are loaded into the applications. """
        # if auto fencing activated, get authorization from remote Supvisors instance by port-knocking
        if self.supvisors.options.auto_fence and not self.authorized(status.address_name):
            self.logger.warn('local is not authorized to deal with {}'.format(status.address_name))
            self.invalid(status)
        else:
            self.logger.info('local is authorized to deal with {}'.format(status.address_name))
            # refresh supervisor information
            self.supvisors.pool.async_process_info(status.address_name)

    def on_tick_event(self, address, event):
        """ Method called upon reception of a tick event from the remote Supvisors instance, telling that it is active.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method also updates the times of the corresponding AddressStatus and the ProcessStatus depending on it.
        Finally, the updated AddressStatus is published. """
        if self.address_mapper.valid(address):
            status = self.addresses[address]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                self.logger.debug('got tick {} from location={}'.format(event, address))
                if status.state != AddressStates.RUNNING:
                    self.check_address(status)
                # re-test isolation status as it may have been changed by the check_address
                if not status.in_isolation():
                    status.state = AddressStates.RUNNING
                    status.update_times(event['when'], int(time()))
                    # publish AddressStatus event
                    self.supvisors.publisher.send_address_status(status)
        else:
            self.logger.warn('got tick from unexpected location={}'.format(addresses))

    def on_process_event(self, address, event):
        """ Method called upon reception of a process event from the remote Supvisors instance.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method updates the ProcessStatus corresponding to the event, and thus the wrapping ApplicationStatus.
        Finally, the updated ProcessStatus and ApplicationStatus are published. """
        if self.address_mapper.valid(address):
            status = self.addresses[address]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                self.logger.debug('got event {} from location={}'.format(event, address))
                try:
                    # refresh process info from process event
                    process = self.process_from_event(event)
                except KeyError:
                    # process not found. normal when no tick yet received from this address
                    self.logger.debug('reject event {} from location={}'.format(event, address))
                else:
                    process.update_info(address, event)
                    # refresh application status
                    application = self.applications[process.application_name]
                    application.update_status()
                    # publish ProcessStatus and ApplicationStatus events
                    self.supvisors.publisher.send_process_status(process)
                    self.supvisors.publisher.send_application_status(application)
                    return process
        else:
            self.logger.error('got process event from unexpected location={}'.format(addresses))

    def on_timer_event(self):
        """ Check that all Supvisors instances are still publishing.
        Supvisors considers that there a Supvisors instance is not active if no tick received in last 10s. """
        for status in self.addresses.values():
            if status.state == AddressStates.RUNNING and (time() - status.local_time) > 10:
                self.invalid(status)
                # publish AddressStatus event
                self.supvisors.publisher.send_address_status(status)

    def handle_isolation(self):
        """ Move ISOLATING addresses to ISOLATED and publish related events. """
        addresses = self.isolating_addresses()
        for address in addresses:
            status = self.addresses[address]
            status.state = AddressStates.ISOLATED
            # publish AddressStatus event
            self.supvisors.publisher.send_address_status(status)
        return addresses

    # XML-RPC requets
    def authorized(self, address):
        """ Perform a XML-RPC request towards the Supvisors instance located on address to check that local is not ISOLATED. """
        try:
            status = self.supvisors.requester.address_info(address, self.address_mapper.local_address)
        except RPCError:
            self.logger.critical('[BUG] could not get address info from running remote supervisor {}'.format(address))
            raise
        return AddressStates.from_string(status['state']) not in [AddressStates.ISOLATING, AddressStates.ISOLATED]

    def all_process_info(self, address):
        """ Perform a XML-RPC request to get information about all processes managed by Supervisor on address. """
        try:
            info = self.supvisors.requester.all_process_info(address)
        except RPCError:
            self.logger.critical('[BUG] could not get all process info from running remote supervisor {}'.format(address))
            raise
        return info
