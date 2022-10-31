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

from typing import List

from .application import ApplicationRules, ApplicationStatus
from .instancestatus import *
from .process import *
from .publisherinterface import EventPublisherInterface
from .ttypes import ApplicationStates, SupvisorsInstanceStates, CLOSING_STATES, NameList, PayloadList, LoadMap


class Context(object):
    """ The Context class holds the main data of Supvisors:

    - instances: the dictionary of all SupvisorsInstanceStatus (key is Supvisors identifier) ;
    - local_identifier: the identifier of the local Supvisors instance ;
    - local_instance: the SupvisorsInstanceStatus of the local Supvisors instance ;
    - applications: the dictionary of all ApplicationStatus (key is application name) ;
    - master_identifier: the name of the Supvisors master ;
    - is_master: a boolean telling if the local Supvisors instance is the master instance ;
    - start_date: the date since Supvisors entered the INITIALIZATION state ;
    - local_sequence_counter: the last sequence counter received from the local TICK.
    """

    # annotation types
    InstancesMap = Dict[str, SupvisorsInstanceStatus]
    ApplicationsMap = Dict[str, ApplicationStatus]

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        self.external_publisher: Optional[EventPublisherInterface] = None
        # the Supvisors instances
        self.instances: Context.InstancesMap = {
            identifier: SupvisorsInstanceStatus(supvisors_id, supvisors)
            for identifier, supvisors_id in self.supvisors.supvisors_mapper.instances.items()}
        # the local Supvisors instance
        self.local_identifier: str = self.supvisors.supvisors_mapper.local_identifier
        self.local_instance: SupvisorsInstanceStatus = self.instances[self.local_identifier]
        # the applications known to Supvisors
        self.applications: Context.ApplicationsMap = {}
        # master attributes
        self._master_identifier: str = ''
        self._is_master: bool = False
        # start time to manage end of synchronization phase
        self.start_date: float = 0.0
        # last local TICK sequence counter, used for node invalidation
        self.local_sequence_counter: int = 0
        # keep history of last state and modes publication
        self.last_state_modes = None

    def reset(self) -> None:
        """ Reset the context to prepare a new synchronization phase.

        :return: None
        """
        self.master_identifier = ''
        self.start_date = time()
        for status in self.instances.values():
            status.reset()
        # store the reference to the external publisher
        self.external_publisher = self.supvisors.external_publisher

    @property
    def master_identifier(self) -> str:
        return self._master_identifier

    @property
    def is_master(self) -> bool:
        return self._is_master

    @master_identifier.setter
    def master_identifier(self, identifier) -> None:
        self.logger.info(f'Context.master_identifier: {identifier}')
        self._master_identifier = identifier
        self._is_master = identifier == self.local_identifier

    def publish_state_modes(self, event: Payload) -> None:
        """ Publish the Supvisors instance state and modes.
        This information is provided internally by the local Supvisors instance, and it will be published to all
        connected Supvisors instances.

        :param event: the state or the mode updated
        :return: None
        """
        # keys are Starter, Stopper, fsm_state
        # internal update due to FSM state change or Starter / Stopper progress change
        changed, state_modes = self.local_instance.apply_state_modes(event)
        if changed:
            # on change, publish the local Supvisors state and modes to the other Supvisors instances
            self.supvisors.sockets.publisher.send_state_event(state_modes.serial())

    def get_state_modes(self) -> Payload:
        """ Get the Supvisors state and modes, based on all connected Supvisors instances.
        Supvisors state is the FSM state and is a reflection of the Supvisors Master instance state.
        Supvisors modes consist in the existence of starting or stopping jobs across all connected Supvisors instances.

        :return: the Supvisors state and the identifiers of the Supvisors instances having starting or stopping jobs
        """
        payload = self.local_instance.state_modes.serial()
        # overwrite starting_jobs and starting_jobs based on a synthesis of modes in all Supvisors instances
        payload.update({'starting_jobs': [identifier for identifier, status in self.instances.items()
                                          if status.state_modes.starting_jobs],
                        'stopping_jobs': [identifier for identifier, status in self.instances.items()
                                          if status.state_modes.stopping_jobs]})
        return payload

    def _publish_state_mode(self) -> None:
        """ Publish the new state and modes if it differs from the latest publication.

        :return: None
        """
        current_state_modes = self.get_state_modes()
        if self.last_state_modes != current_state_modes:
            self.last_state_modes = current_state_modes
            self.external_publisher.send_supvisors_status(current_state_modes)

    def get_nodes_load(self) -> LoadMap:
        """ Get the Supvisors instances load grouped by node.

        :return: The nodes load
        """
        return {ip_address: sum(self.instances[identifier].get_load() for identifier in identifiers)
                for ip_address, identifiers in self.supvisors.supvisors_mapper.nodes.items()}

    # methods on instances
    def unknown_identifiers(self) -> NameList:
        """ Return the identifiers of the Supervisor instances in UNKNOWN state. """
        return self.instances_by_states([SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING,
                                         SupvisorsInstanceStates.ISOLATING])

    def running_identifiers(self) -> NameList:
        """ Return the identifiers of the Supervisor instances in RUNNING state. """
        return self.instances_by_states([SupvisorsInstanceStates.RUNNING])

    def running_core_identifiers(self) -> bool:
        """ Check if core SupvisorsInstanceStatus are in RUNNING state.

        :return: True if all core SupvisorsInstanceStatus are in RUNNING state
        """
        if self.supvisors.supvisors_mapper.core_identifiers:
            identifiers = self.running_identifiers()
            return all(identifier in identifiers for identifier in self.supvisors.supvisors_mapper.core_identifiers)

    def isolating_instances(self) -> NameList:
        """ Return the identifiers of the Supervisor instances in ISOLATING state. """
        return self.instances_by_states([SupvisorsInstanceStates.ISOLATING])

    def isolation_instances(self) -> NameList:
        """ Return the identifiers of the Supervisors in ISOLATING or ISOLATED state. """
        return self.instances_by_states([SupvisorsInstanceStates.ISOLATING, SupvisorsInstanceStates.ISOLATED])

    def active_instances(self) -> NameList:
        """ Return the identifiers of the Supervisors NOT in ISOLATING or ISOLATED state. """
        return self.instances_by_states([SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.CHECKING,
                                         SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.SILENT])

    def instances_by_states(self, states: List[SupvisorsInstanceStates]) -> NameList:
        """ Return the Supervisor identifiers sorted by Supervisor state. """
        return [identifier for identifier, status in self.instances.items() if status.state in states]

    def invalid(self, status: SupvisorsInstanceStatus, fence=None) -> None:
        """ Declare SILENT or ISOLATING the SupvisorsInstanceStatus in parameter, according to the auto_fence option.
        The local Supvisors instance is never ISOLATING, whatever the option is set or not.
        Always give it a chance to restart. """
        if status.identifier == self.local_identifier:
            # this is very unlikely
            # 1. invalidation by end of sync would mean that the SupvisorsMainLoop thread is broken and unable to
            #    provide ticks, which is a critical failure
            # 2. invalidation by timer is impossible as is it driven by the local TICK
            #    a Supvisors instance cannot have a counter shift with itself
            # 3. on_authorization - the local Supvisors instance cannot be ISOLATED from itself by design
            #    that's precisely the aim of the following instructions
            # 4. a discrepancy has been detected between the internal context and the process events received
            #    a new CHECKING phase is required
            self.logger.critical('Context.invalid: local Supvisors instance is either SILENT or inconsistent')
            status.state = SupvisorsInstanceStates.SILENT
        elif fence or self.supvisors.options.auto_fence:
            status.state = SupvisorsInstanceStates.ISOLATING
        else:
            status.state = SupvisorsInstanceStates.SILENT
        # publish SupvisorsInstanceStatus and SupvisorsStatus
        if self.external_publisher:
            self.external_publisher.send_instance_status(status.serial())
            self._publish_state_mode()

    # methods on applications / processes
    def get_managed_applications(self) -> Dict[str, ApplicationStatus]:
        """ Get the managed applications (as defined in rules file).

        :return: the managed applications
        """
        return {application_name: application for application_name, application in self.applications.items()
                if application.rules.managed}

    def is_namespec(self, namespec: str) -> bool:
        """ Check if the namespec is valid with the context.

        :return: True if the namespec is valid
        """
        application_name, process_name = split_namespec(namespec)
        if application_name not in self.applications:
            return False
        if process_name:
            application_status = self.applications[application_name]
            return process_name in application_status.processes
        return True

    def get_process(self, namespec: str) -> Optional[ProcessStatus]:
        """ Return the ProcessStatus corresponding to the namespec.

        :param namespec: the process namespec
        :return: the corresponding ProcessStatus
        """
        application_name, process_name = split_namespec(namespec)
        return self.applications[application_name].processes[process_name]

    def find_runnable_processes(self, regex: str) -> List[ProcessStatus]:
        """ Get all processes whose namespec matches the regex.
        The processes shall not be already running.

        :return: the candidate processes
        """
        return [process for application in self.applications.values()
                for process in application.processes.values()
                if re.search(rf'{regex}', process.namespec) and not process.running()]

    def conflicting(self) -> bool:
        """ Check if any conflicting ProcessStatus is detected.

        :return: True if at least one conflict is detected
        """
        return any((process.conflicting() for application in self.applications.values()
                    for process in application.processes.values()
                    if application.rules.managed))

    def conflicts(self) -> List[ProcessStatus]:
        """ Get all conflicting processes.

        :return: the list of conflicting ProcessStatus
        """
        return [process for application in self.applications.values()
                for process in application.processes.values()
                if application.rules.managed and process.conflicting()]

    def setdefault_application(self, application_name: str) -> Optional[ApplicationStatus]:
        """ Return the application corresponding to application_name if found,
        otherwise load rules from the rules file, create a new application entry if rules exist and return it.
        Applications that are not defined in the rules files will not be stored in the Supvisors context.

        :param application_name: the name of the application
        :return: the application stored in the Supvisors context
        """
        # find existing application
        application = self.applications.get(application_name)
        if not application:
            # load rules from rules file
            rules = ApplicationRules(self.supvisors)
            if self.supvisors.parser:
                # apply default starting strategy from options
                rules.starting_strategy = self.supvisors.options.starting_strategy
                self.supvisors.parser.load_application_rules(application_name, rules)
                self.logger.debug(f'Context.setdefault_application: application={application_name} rules={rules}')
            # create new instance
            application = ApplicationStatus(application_name, rules, self.supvisors)
            self.applications[application_name] = application
        return application

    def setdefault_process(self, info: Payload) -> Optional[ProcessStatus]:
        """ Return the process corresponding to info if found,
        otherwise load rules from the rules file, create a new process entry if rules exist and return it.
        Processes that are not defined in the rules files will not be stored in the Supvisors context.

        :param info: the payload representing the process
        :return: the process stored in the Supvisors context
        """
        application_name, process_name = info['group'], info['name']
        namespec = make_namespec(application_name, info['name'])
        # get application
        application = self.setdefault_application(application_name)
        # search for existing process in application
        process = application.processes.get(process_name)
        if not process:
            # by default, apply application starting / running failure strategies
            rules = ProcessRules(self.supvisors)
            rules.starting_failure_strategy = application.rules.starting_failure_strategy
            rules.running_failure_strategy = application.rules.running_failure_strategy
            if self.supvisors.parser:
                # load rules from rules file
                self.supvisors.parser.load_program_rules(namespec, rules)
                self.logger.debug(f'Context.setdefault_process: namespec={namespec} rules={rules}')
            # add new process to context
            process = ProcessStatus(application_name, info['name'], rules, self.supvisors)
            application.add_process(process)
        return process

    def load_processes(self, identifier: str, all_info: PayloadList) -> None:
        """ Load application dictionary from the process information received from the remote Supvisors.

        :param identifier: the identifier of the Supvisors instance
        :param all_info: the process information got from the node
        :return: None
        """
        self.logger.trace(f'Context.load_processes: identifier={identifier} all_info={all_info}')
        # get SupvisorsInstanceStatus corresponding to identifier
        status = self.instances[identifier]
        # store processes into their application entry
        for info in all_info:
            # get or create process
            process = self.setdefault_process(info)
            if process:
                # update the current entry
                process.add_info(identifier, info)
                # share the instance to the Supervisor instance that holds it
                status.add_process(process)
        # re-evaluate application sequences and status
        for application in self.applications.values():
            application.update_sequences()
            application.update_status()

    # methods on events
    def on_instance_state_event(self, identifier: str, event: Payload) -> None:
        """ Update the Supvisors instance state and modes.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param event: the new state and modes
        :return: None
        """
        # check if identifier is known
        if not self.supvisors.supvisors_mapper.valid(identifier):
            self.logger.warn(f'Context.on_authorization: auth received from unexpected Supvisors={identifier}')
            return
        # ISOLATING / ISOLATED instances are not updated anymore
        # should not happen as the subscriber should have been disconnected but there may be a tick in the pipe
        status = self.instances[identifier]
        if not status.in_isolation():
            # Supvisors state notification: update the Supvisors instance status
            # WARN: local instance is already up-to-date, could even be a step beyond
            if identifier != self.local_identifier:
                status.update_state_modes(event)
            # publish the new Supvisors status
            if self.external_publisher:
                self._publish_state_mode()

    def on_authorization(self, identifier: str, authorized: Optional[bool]) -> bool:
        """ Method called upon reception of an authorization event telling if the remote Supvisors instance
        authorizes the local Supvisors instance to process its events.

        :param identifier: the identifier of the Supvisors instance that sent the event
        :param authorized: the node authorization status
        :return: True if authorized both ways
        """
        # check if identifier is known
        if not self.supvisors.supvisors_mapper.valid(identifier):
            self.logger.warn(f'Context.on_authorization: auth received from unexpected Supvisors={identifier}')
            return False
        # check Supvisors instance state
        status = self.instances[identifier]
        if status.state != SupvisorsInstanceStates.CHECKING:
            self.logger.error(f'Context.on_authorization: auth rejected from non-CHECKING Supvisors={identifier}')
            return False
        # process authorization status
        if authorized is None:
            # the check call in SupvisorsMainLoop failed
            # the remote Supvisors instance is likely restarting or shutting down so defer
            self.logger.warn(f'Context.on_authorization: failed to get auth status from Supvisors={identifier}')
            self.invalid(status)
        elif not authorized:
            self.logger.warn('Context.on_authorization: local Supvisors instance is isolated by Supvisors={identifier}')
            self.invalid(status, True)
        else:
            self.logger.info(f'Context.on_authorization: local Supvisors instance is authorized to work with'
                             f' Supvisors={identifier}')
            status.state = SupvisorsInstanceStates.RUNNING
            return True
        return False

    def on_tick_event(self, identifier: str, event: Payload) -> None:
        """ Method called upon reception of a tick event from the remote Supvisors instance, telling that it is active.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method also updates the times of the corresponding SupvisorsInstanceStatus and its ProcessStatus.
        Finally, the updated SupvisorsInstanceStatus is published.

        :param identifier: the identifier of the Supvisors instance from which the event has been received
        :param event: the TICK event sent
        :return: None
        """
        # check if identifier is known
        if not self.supvisors.supvisors_mapper.valid(identifier):
            self.logger.error(f'Context.on_tick_event: got tick from unknown Supvisors={identifier}')
            return
        # check if local tick has been received yet
        if identifier != self.local_identifier:
            if self.local_instance.state != SupvisorsInstanceStates.RUNNING:
                self.logger.debug('Context.on_tick_event: waiting for local tick first')
                return
        # process node event
        status = self.instances[identifier]
        # ISOLATING / ISOLATED instances are not updated anymore
        # should not happen as the subscriber should have been disconnected but there may be a tick in the pipe
        if not status.in_isolation():
            self.logger.debug(f'Context.on_tick_event: got tick {event} from Supvisors={identifier}')
            # check sequence counter to identify rapid supervisor restart
            if (status.state in [SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.RUNNING]
                    and event['sequence_counter'] < status.sequence_counter):
                self.logger.warn(f'Context.on_tick_event: stealth restart of Supvisors={identifier}')
                # it's not enough to change the instance status as some handling may be required on running processes
                # so force node inactivity by resetting its local_sequence_counter
                # FSM on_timer_event will handle the node invalidation
                status.local_sequence_counter = 0
            else:
                # update internal times
                status.update_times(event['sequence_counter'], event['when'], self.local_sequence_counter, time())
                # check node
                if status.state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.SILENT]:
                    self.check_instance(status)
                # publish SupvisorsInstanceStatus and SupvisorsStatus events
                if self.external_publisher:
                    self.external_publisher.send_instance_status(status.serial())
                    self._publish_state_mode()

    def on_timer_event(self, event: Payload) -> Tuple[NameList, Set[ProcessStatus]]:
        """ Check that all Supvisors instances are still publishing.
        Supvisors considers that there a Supvisors instance is not active if no tick received in last 10s.

        :param event: the local tick event
        :return: the identifiers of the invalidated Supvisors instances and the processes in failure
        """
        invalidated_identifiers, process_failures = [], set({})  # strange but avoids IDE warning on annotations
        # find all Supvisors instances that did not send their periodic tick
        current_time = event['when']
        self.local_sequence_counter = event['sequence_counter']
        # do not check for invalidation before synchro_timeout
        if (current_time - self.start_date) > self.supvisors.options.synchro_timeout:
            # check all Supvisors instances
            for status in self.instances.values():
                if status.state == SupvisorsInstanceStates.UNKNOWN:
                    # invalid unknown Supvisors instances
                    # nothing to do on processes as none received yet
                    self.invalid(status)
                elif status.inactive(self.local_sequence_counter):
                    # invalid silent Supvisors instances
                    self.invalid(status)
                    invalidated_identifiers.append(status.identifier)
                    # for processes that were running on node, invalidate node in process
                    # WARN: decision is made NOT to remove the node payload from the ProcessStatus and NOT to remove
                    # the ProcessStatus from the Context if no more node payload left.
                    # The aim is to keep a trace in the Web UI about the application processes that have been lost
                    # and their related description.
                    process_failures.update({process for process in status.running_processes()
                                             if process.invalidate_identifier(status.identifier)})
            # publish process status in failure
            if self.external_publisher:
                for process in process_failures:
                    self.external_publisher.send_process_status(process.serial())
            # update all application sequences and status
            for application_name in {process.application_name for process in process_failures}:
                application = self.applications[application_name]
                # update sequence useless as long as the application.process map is not impacted (see decision above)
                # application.update_sequences()
                application.update_status()
                if self.external_publisher:
                    self.external_publisher.send_application_status(application.serial())
        #  return the identifiers of all invalidated Supvisors instances and the processes declared in failure
        return invalidated_identifiers, process_failures

    def check_process(self, instance_status: SupvisorsInstanceStatus,
                      event: Payload, check_source=True) -> Optional[Tuple[ApplicationStatus, ProcessStatus]]:
        """ Check and return the internal data corresponding to the process event.

        :param instance_status: the Supvisors instance from which the event has been received
        :param event: the event payload
        :param check_source: if True, the process should contain information related to the Supvisors instance
        :return: None
        """
        application_name, process_name = event['group'], event['name']
        try:
            application = self.applications[application_name]
            if process_name == '*':
                process = None
            else:
                process = application.processes[process_name]
                assert not check_source or instance_status.identifier in process.info_map
            return application, process
        except (AssertionError, KeyError):
            namespec = make_namespec(application_name, process_name)
            # if the event is received during a Supvisors closing state, it can be ignored
            # otherwise, it means that there's a discrepancy in the internal context, which requires CHECKING
            if self.supvisors.fsm.state in CLOSING_STATES:
                self.logger.warn(f'Context.check_process: ignoring unknown event about process={namespec}'
                                 f' received from Supvisors={instance_status.identifier} while in'
                                 f' {self.supvisors.fsm.state} state')
            else:
                self.logger.error(f'Context.check_process: CHECKING required due to unknown event about'
                                  f' process={namespec} received from Supvisors={instance_status.identifier}')
                self.invalid(instance_status)

    def on_process_removed_event(self, identifier: str, event: Payload) -> None:
        """ Method called upon reception of a process removed event from the remote Supvisors instance.
        Following an XML-RPC update_numprocs, the size of homogeneous process groups may decrease and lead to removal
        of processes.
        A call to the XML-RPC removeProcessGroup triggers this event too.

        :param identifier: the identifier of the Supvisors instance from which the event has been received
        :param event: the event payload
        :return: None
        """
        if self.supvisors.supvisors_mapper.valid(identifier):
            instance_status = self.instances[identifier]
            # accept events only in RUNNING state
            if instance_status.state == SupvisorsInstanceStates.RUNNING:
                self.logger.debug(f'Context.on_remove_process_event: got event {event} from Supvisors={identifier}')
                # get internal data
                app_proc = self.check_process(instance_status, event)
                if app_proc:
                    application_impacted = False
                    # get process targets
                    application, event_process = app_proc
                    processes = [event_process] if event_process else application.get_instance_processes(identifier)
                    for process in processes:
                        # WARN: process_failures are not triggered here as the processes have been properly stopped
                        #  as a consequence of the user action
                        # In order to inform users on Supvisors event interface, a fake state DELETED (-1) is sent
                        process_event = event.copy()
                        process_event.update({'name': process.process_name, 'state': -1})
                        if self.external_publisher:
                            self.external_publisher.send_process_event(identifier, process_event)
                        # remove process from instance_status
                        instance_status.remove_process(process)
                        # delete the process info entry related to the node
                        if process.remove_identifier(identifier):
                            if self.external_publisher:
                                # publish a last process status before it is deleted
                                payload = process.serial()
                                payload.update({'statecode': -1, 'statename': 'DELETED'})
                                self.external_publisher.send_process_status(payload)
                            # there's no more Supvisors instance supporting the process definition
                            # so remove the process from the application
                            application.remove_process(process.process_name)
                            application_impacted = True
                    # an update of numprocs cannot leave the application empty (update_numprocs 0 not allowed)
                    # however, a remove_group can induce this situation
                    if not application.processes:
                        application.state = ApplicationStates.DELETED
                        del self.applications[application.application_name]
                    # send an application status when impacted
                    if application_impacted and self.external_publisher:
                        self.external_publisher.send_application_status(application.serial())

    def on_process_disability_event(self, identifier: str, event: Payload) -> None:
        """ Method called upon reception of a process enabled event from the remote Supvisors instance.
        Following an XML-RPC enable/disable on a program, the corresponding process are allowed to be started or not.

        :param identifier: the identifier of the Supvisors instance from which the event has been received
        :param event: the event payload
        :return: None
        """
        if self.supvisors.supvisors_mapper.valid(identifier):
            instance_status = self.instances[identifier]
            # accept events only in RUNNING state
            if instance_status.state == SupvisorsInstanceStates.RUNNING:
                self.logger.debug(f'Context.on_process_enabled_event: got event {event} from Supvisors={identifier}')
                # get internal data
                app_proc = self.check_process(instance_status, event)
                if app_proc:
                    process = app_proc[1]
                    # update the process info entry related to the node
                    process.update_disability(identifier, event['disabled'])
                    # at the moment, process disability has no impact on the application and process status
                    # so only the process event publication makes sense
                    if self.external_publisher:
                        self.external_publisher.send_process_event(identifier, event)

    def on_process_state_event(self, identifier: str, event: Payload) -> Optional[ProcessStatus]:
        """ Method called upon reception of a process event from the remote Supvisors instance.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method updates the ProcessStatus corresponding to the event, and thus the wrapping ApplicationStatus.
        Finally, the updated ProcessStatus and ApplicationStatus are published.

        :param identifier: the identifier of the Supvisors instance from which the event has been received
        :param event: the event payload
        :return: None
        """
        if self.supvisors.supvisors_mapper.valid(identifier):
            instance_status = self.instances[identifier]
            # accept events only in RUNNING state
            if instance_status.state == SupvisorsInstanceStates.RUNNING:
                self.logger.debug(f'Context.on_process_event: got event {event} from Supvisors={identifier}')
                # WARN: the Master may send a process event corresponding to a process that is not configured in it
                forced_event = 'forced' in event
                app_proc = self.check_process(instance_status, event, not forced_event)
                if not app_proc:
                    self.logger.trace('Context.on_process_event: could not find any process corresponding'
                                      f' to event={event}')
                else:
                    application, process = app_proc
                    updated = True
                    # refresh process info depending on the nature of the process event
                    if forced_event:
                        updated = process.force_state(event)
                        self.logger.trace(f'Context.on_process_event: {process.namespec} forced event'
                                          f' considered={updated}')
                        if updated:
                            # remove the 'forced' status before publication
                            event['state'] = process.state
                            del event['forced']
                            del event['identifier']
                    else:
                        # update the ProcessStatus based on new information received from a local Supvisors instance
                        process.update_info(identifier, event)
                        try:
                            # update command line in Supervisor
                            self.supvisors.supervisor_data.update_extra_args(process.namespec, event['extra_args'])
                        except KeyError:
                            # process not found in Supervisor internal structure
                            self.logger.debug(f'Context.on_process_event: cannot apply extra args to {process.namespec}'
                                              ' unknown to local Supervisor')
                    # forced event may be dismissed
                    if updated:
                        # refresh application status
                        application.update_status()
                        # publish process event, status and application status
                        if self.external_publisher:
                            self.external_publisher.send_process_event(identifier, event)
                            self.external_publisher.send_process_status(process.serial())
                            self.external_publisher.send_application_status(application.serial())
                        return process
        else:
            self.logger.error(f'Context.on_process_event: got process event from unknown Supvisors={identifier}')

    def check_instance(self, status) -> None:
        """ Asynchronous port-knocking used to check how the remote Supvisors instance considers the local instance.
        Also used to get the full process list from the node

        :param status: the Supvisors instance to check
        :return: None
        """
        status.state = SupvisorsInstanceStates.CHECKING
        self.supvisors.sockets.pusher.send_check_instance(status.identifier)

    def handle_isolation(self) -> NameList:
        """ Move ISOLATING Supvisors instances to ISOLATED and publish related events. """
        identifiers = self.isolating_instances()
        for identifier in identifiers:
            status = self.instances[identifier]
            status.state = SupvisorsInstanceStates.ISOLATED
            # publish SupvisorsInstanceStatus and SupvisorsStatus events
            if self.external_publisher:
                self.external_publisher.send_instance_status(status.serial())
                self._publish_state_mode()
        return identifiers
