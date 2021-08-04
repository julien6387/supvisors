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

from typing import Iterator, List, Set

from .address import *
from .application import ApplicationRules, ApplicationStatus
from .infosource import SupervisordSource
from .listener import SupervisorListener
from .process import *
from .ttypes import AddressStates, NameList, PayloadList


class Context(object):
    """ The Context class holds the main data of Supvisors:

    - addresses: the dictionary of all AddressStatus (key is address),
    - forced_addresses: the dictionary of the minimal set of AddressStatus (key is address),
    - applications: the dictionary of all ApplicationStatus (key is application name),
    - master_address: the address of the Supvisors master,
    - master: a boolean telling if the local address is the master address.
    - new: a boolean telling if this context has just been started.
    """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        self.logger = supvisors.logger
        # attributes
        self.nodes: Dict[str, AddressStatus] = {node_name: AddressStatus(node_name, self.logger)
                                                for node_name in self.supvisors.address_mapper.node_names}
        self.forced_nodes: Dict[str, AddressStatus] = {node_name: status
                                                       for node_name, status in self.nodes.items()
                                                       if node_name in self.supvisors.options.force_synchro_if}
        self.applications: Dict[str, ApplicationStatus] = {}
        # master attributes
        self._master_node_name = ''
        self._is_master = False
        self.master_operational = False

    def reset(self) -> None:
        """ Reset the context to prepare a new synchronization phase.
        Keep only the nodes definition.

        :return: None
        """
        self.master_node_name = ''
        for status in self.nodes.values():
            status.reset()

    @property
    def master_node_name(self) -> str:
        return self._master_node_name

    @property
    def is_master(self) -> bool:
        return self._is_master

    @master_node_name.setter
    def master_node_name(self, node_name) -> None:
        self.logger.info('Context.master_node_name: {}'.format(node_name))
        self._master_node_name = node_name
        self._is_master = node_name == self.supvisors.address_mapper.local_node_name
        self.master_operational = False

    # methods on nodes
    def unknown_nodes(self) -> NameList:
        """ Return the AddressStatus instances in UNKNOWN state. """
        return self.nodes_by_states([AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.ISOLATING])

    def unknown_forced_nodes(self) -> NameList:
        """ Return the AddressStatus instances in UNKNOWN state. """
        return [status.address_name
                for status in self.forced_nodes.values()
                if status.state in [AddressStates.UNKNOWN, AddressStates.CHECKING, AddressStates.ISOLATING]]

    def running_nodes(self) -> NameList:
        """ Return the AddressStatus instances in RUNNING state. """
        return self.nodes_by_states([AddressStates.RUNNING])

    def isolating_nodes(self) -> NameList:
        """ Return the AddressStatus instances in ISOLATING state. """
        return self.nodes_by_states([AddressStates.ISOLATING])

    def isolation_nodes(self) -> NameList:
        """ Return the AddressStatus instances in ISOLATING or ISOLATED state. """
        return self.nodes_by_states([AddressStates.ISOLATING, AddressStates.ISOLATED])

    def nodes_by_states(self, states: List[AddressStates]) -> NameList:
        """ Return the AddressStatus instances sorted by state. """
        return [status.address_name
                for status in self.nodes.values()
                if status.state in states]

    def invalid(self, status: AddressStatus) -> None:
        """ Declare SILENT or ISOLATING the AddressStatus in parameter, according to the auto_fence option.
        A local node is never ISOLATING, whatever the option is set or not.
        Give it a chance to restart. """
        if status.address_name == self.supvisors.address_mapper.local_node_name:
            # this is very unlikely
            # to get here, 2 ways:
            #    1. end_synchro or on_timer_event
            #       both are triggered directly by the FSM upon supervisor ticks so local node is definitely not SILENT
            #       possible causes would be: network congestion, CPU overload or broken internal publisher
            #       and thus the AddressStatus.local_time would not be updated
            #    2. on_authorization
            #       by design, the local node cannot be ISOLATED. that's precisely the aim of the following instructions
            self.logger.critical('Context.invalid: local node is SILENT')
            status.state = AddressStates.SILENT
        elif self.supvisors.options.auto_fence:
            status.state = AddressStates.ISOLATING
        else:
            status.state = AddressStates.SILENT

    def end_synchro(self) -> None:
        """ Declare as SILENT the nodes that are still not responsive at the end of the INITIALIZATION state.

        :return: None
        """
        # consider problem if no tick received at the end of synchro time
        for status in self.nodes.values():
            if status.state == AddressStates.UNKNOWN:
                self.invalid(status)

    # methods on applications / processes
    def get_managed_applications(self) -> Iterator[ApplicationStatus]:
        """ Return the managed applications (defined in rules file). """
        return filter(lambda x: x.rules.managed, self.applications.values())

    def get_all_namespecs(self) -> NameList:
        """ Return the ProcessStatus corresponding to the namespec. """
        return list({process.namespec for application in self.applications.values()
                     for process in application.processes.values()})

    def get_process(self, namespec: str) -> Optional[ProcessStatus]:
        """ Return the ProcessStatus corresponding to the namespec. """
        application_name, process_name = split_namespec(namespec)
        return self.applications[application_name].processes[process_name]

    def conflicting(self):
        """ Return True if any conflicting ProcessStatus is detected. """
        return any((process.conflicting() for application in self.applications.values()
                    for process in application.processes.values()
                    if application.rules.managed))

    def conflicts(self):
        """ Return all conflicting ProcessStatus. """
        return [process for application in self.applications.values()
                for process in application.processes.values()
                if application.rules.managed and process.conflicting()]

    def setdefault_application(self, application_name: str) -> Optional[ApplicationStatus]:
        """ Return the application corresponding to application_name if found.
        Otherwise load rules from the rules file, create a new application entry if rules exist and return it.
        Applications that are not defined in the rules files will not be stored in the Supvisors context.

        :param application_name: the name of the application
        :return: the application stored in the Supvisors context
        """
        # find existing application
        application = self.applications.get(application_name)
        if not application:
            # load rules from rules file
            rules = ApplicationRules()
            if self.supvisors.parser:
                # apply default starting strategy from options
                rules.starting_strategy = self.supvisors.options.starting_strategy
                self.supvisors.parser.load_application_rules(application_name, rules)
                self.logger.debug('Context.setdefault_application: application={} rules={}'
                                  .format(application_name, rules))
            # create new instance
            application = ApplicationStatus(application_name, rules, self.supvisors)
            self.applications[application_name] = application
        return application

    def setdefault_process(self, info: Payload) -> Optional[ProcessStatus]:
        """ Return the process corresponding to info if found.
        Otherwise load rules from the rules file, create a new process entry if rules exist and return it.
        Processes that are not defined in the rules files will not be stored in the Supvisors context.

        :param info: the payload representing the process
        :return: the process stored in the Supvisors context
        """
        application_name, process_name = info['group'], info['name']
        namespec = make_namespec(application_name, info['name'])
        # get application
        application = self.setdefault_application(application_name)
        self.logger.debug('Context.setdefault_process: application={}'.format(application.application_name))
        # search for existing process in application
        process = application.processes.get(process_name)
        if not process:
            # apply default running failure strategy
            rules = ProcessRules(self.supvisors)
            rules.running_failure_strategy = application.rules.running_failure_strategy
            if self.supvisors.parser:
                # load rules from rules file
                self.supvisors.parser.load_process_rules(namespec, rules)
                self.logger.debug('Context.setdefault_process: namespec={} rules={}'.format(namespec, rules))
            # add new process to context
            process = ProcessStatus(application_name, info['name'], rules, self.supvisors)
            application.add_process(process)
        return process

    def load_processes(self, node_name: str, all_info: PayloadList) -> None:
        """ Load application dictionary from process info got from Supervisor on address. """
        self.logger.trace('Context.load_processes: node_name={} all_info={}'.format(node_name, all_info))
        # get AddressStatus corresponding to address
        status = self.nodes[node_name]
        # store processes into their application entry
        for info in all_info:
            # get or create process
            process = self.setdefault_process(info)
            if process:
                # update the current entry
                process.add_info(node_name, info)
                # share the instance to the Supervisor instance that holds it
                status.add_process(process)

    # methods on events
    def on_authorization(self, node_name: str, authorized: bool) -> Optional[bool]:
        """ Method called upon reception of an authorization event telling if the remote Supvisors instance
        authorizes the local Supvisors instance to process its events.

        :param node_name: the node name from which comes the event
        :param authorized: the node authorization status
        :return: True if authorized both ways
        """
        if self.supvisors.address_mapper.valid(node_name):
            status = self.nodes[node_name]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                if authorized:
                    self.logger.info('Context.on_authorization: local is authorized to deal with {}'.format(node_name))
                    status.state = AddressStates.RUNNING
                    return True
                self.logger.warn('Context.on_authorization: local is not authorized to deal with {}'.format(node_name))
                self.invalid(status)
        else:
            self.logger.warn('Context.on_authorization: got authorization from unexpected node={}'.format(node_name))

    def on_tick_event(self, node_name: str, event):
        """ Method called upon reception of a tick event from the remote Supvisors instance, telling that it is active.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method also updates the times of the corresponding AddressStatus and the ProcessStatus depending on it.
        Finally, the updated AddressStatus is published. """
        if self.supvisors.address_mapper.valid(node_name):
            status = self.nodes[node_name]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                self.logger.debug('Context.on_tick_event: got tick {} from location={}'.format(event, node_name))
                # asynchronous port-knocking used to check if remote Supvisors instance considers
                # the local instance as isolated
                if status.state in [AddressStates.UNKNOWN, AddressStates.SILENT]:
                    status.state = AddressStates.CHECKING
                    self.supvisors.zmq.pusher.send_check_node(node_name)
                # update internal times
                status.update_times(event['when'], int(time()))
                # publish AddressStatus event
                self.supvisors.zmq.publisher.send_address_status(status.serial())
        else:
            self.logger.warn('Context.on_tick_event: got tick from unexpected location={}'.format(node_name))

    def on_process_event(self, node_name: str, event: Payload) -> Optional[ProcessStatus]:
        """ Method called upon reception of a process event from the remote Supvisors instance.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method updates the ProcessStatus corresponding to the event, and thus the wrapping ApplicationStatus.
        Finally, the updated ProcessStatus and ApplicationStatus are published.
        """
        if self.supvisors.address_mapper.valid(node_name):
            status = self.nodes[node_name]
            # ISOLATED address is not updated anymore
            if not status.in_isolation():
                self.logger.debug('Context.on_process_event: got event {} from node={}'.format(event, node_name))
                try:
                    # get internal data
                    application = self.applications[event['group']]
                    process = application.processes[event['name']]
                except KeyError:
                    # process not found in Supvisors internal structure
                    # expected when no tick received yet from this node
                    self.logger.debug('Context.on_process_event: reject event {} from node={} as program unknown'
                                      ' to local Supvisors'.format(event, node_name))
                else:
                    # refresh process info depending on the nature of the process event
                    if 'forced' in event:
                        process.force_state(event)
                        del event['forced']
                    else:
                        process.update_info(node_name, event)
                        try:
                            # update command line in Supervisor
                            self.supvisors.info_source.update_extra_args(process.namespec, event['extra_args'])
                        except KeyError:
                            # process not found in Supervisor internal structure
                            self.logger.warn('Context.on_process_event: cannot apply extra args to {} unknown'
                                             ' to local Supervisor'.format(process.namespec))
                    # refresh application status
                    application = self.applications[process.application_name]
                    application.update_status()
                    # publish process event, status and application status
                    publisher = self.supvisors.zmq.publisher
                    publisher.send_process_event(node_name, event)
                    publisher.send_process_status(process.serial())
                    publisher.send_application_status(application.serial())
                    return process
        else:
            self.logger.error('Context.on_process_event: got process event from unexpected node={}'.format(node_name))

    def on_timer_event(self) -> Set[ProcessStatus]:
        """ Check that all Supvisors instances are still publishing.
        Supvisors considers that there a Supvisors instance is not active if no tick received in last 10s. """
        process_failures = set()
        # find all nodes that do not send their periodic tick
        current_time = time()
        invalid_nodes = [status for status in self.nodes.values() if status.inactive(current_time)]
        for status in invalid_nodes:
            # update node status state
            self.invalid(status)
            # publish AddressStatus event
            self.supvisors.zmq.publisher.send_address_status(status.serial())
            # invalidate node in processes
            process_failures.update({process for process in status.running_processes()
                                     if process.invalidate_node(status.address_name)})
        #  return all processes that declare a failure
        return process_failures

    def handle_isolation(self) -> NameList:
        """ Move ISOLATING addresses to ISOLATED and publish related events. """
        node_names = self.isolating_nodes()
        for node_name in node_names:
            status = self.nodes[node_name]
            status.state = AddressStates.ISOLATED
            # publish AddressStatus event
            self.supvisors.zmq.publisher.send_address_status(status.serial())
        return node_names
