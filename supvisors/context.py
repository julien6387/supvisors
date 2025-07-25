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
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from supervisor.loggers import Logger
from supervisor.options import make_namespec, split_namespec

from .application import ApplicationRules, ApplicationStatus
from .external_com.eventinterface import EventPublisherInterface
from .instancestatus import SupvisorsInstanceStatus
from .internal_com.mapper import SupvisorsMapper
from .process import ProcessRules, ProcessStatus
from .statemodes import SupvisorsStateModes
from .ttypes import (ApplicationStates, SupvisorsInstanceStates, WORKING_STATES,
                     Ipv4Address, NameList, Payload, PayloadList, LoadMap, AuthorizationTypes)

# annotation types
InstancesMap = Dict[str, SupvisorsInstanceStatus]
ApplicationsMap = Dict[str, ApplicationStatus]


class Context:
    """ The Context class holds the main data of Supvisors.

    Attributes are:
        - supvisors: the Supvisors global structure;
        - instances: the dictionary of all SupvisorsInstanceStatus (key is Supvisors identifier);
        - applications: the dictionary of all ApplicationStatus (key is application name);
        - start_date: the date since Supvisors entered the OFF state.
    """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # the Supvisors instances declared statically in the supervisor configuration file
        self.instances: InstancesMap = {identifier: SupvisorsInstanceStatus(supvisors_id, supvisors)
                                        for identifier, supvisors_id in self.mapper.instances.items()}
        # the applications known to Supvisors
        self.applications: ApplicationsMap = {}
        # duration since the entry in Supvisors OFF state
        self.start_date: float = 0.0

    # Shortcuts to Supvisors main objects
    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    @property
    def mapper(self) -> SupvisorsMapper:
        """ Get the Supvisors instances mapper. """
        return self.supvisors.mapper

    @property
    def state_modes(self) -> SupvisorsStateModes:
        """ Get the Supvisors instances mapper. """
        return self.supvisors.state_modes

    @property
    def external_publisher(self) -> Optional[EventPublisherInterface]:
        """ Get the Supvisors external publisher. """
        return self.supvisors.external_publisher

    # Easy access
    @property
    def uptime(self) -> float:
        """ Get the uptime since Supvisors entered in SYNCHRONIZATION state. """
        return time.monotonic() - self.start_date

    # Local instance status and operations
    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.mapper.local_identifier

    @property
    def local_status(self) -> SupvisorsInstanceStatus:
        """ Get the local Supvisors instance structure. """
        return self.instances[self.local_identifier]

    @property
    def local_sequence_counter(self) -> int:
        """ Get last local TICK sequence counter, used for node invalidation. """
        return self.local_status.sequence_counter

    # Master instance status and operations
    @property
    def master_instance(self) -> Optional[SupvisorsInstanceStatus]:
        """ Get local Supvisors instance structure. """
        return self.instances.get(self.state_modes.master_identifier)

    # methods on nodes
    def is_valid(self, identifier: str, nick_identifier: str,
                 ipv4_address: Ipv4Address) -> Optional[SupvisorsInstanceStatus]:
        """ Check the validity of the message emitter.

        Validity is ok if:
            * the identifier is known (at least as a nick identifier) ;
            * the IP address and port fit the corresponding Supvisors instance ;
            * the corresponding Supvisors instance is not declared ISOLATED.
        """
        identifiers = self.mapper.filter([identifier, nick_identifier])
        if len(identifiers) != 1:
            # multiple resolution not expected here
            return None
        status = self.instances[identifiers[0]]
        if not status.isolated and status.supvisors_id.is_valid(ipv4_address):
            return status
        return None

    def get_nodes_load(self) -> LoadMap:
        """ Get the Supvisors instances load grouped by node.

        :return: The nodes load.
        """
        return {machine_id: sum(self.instances[identifier].get_load()
                                for identifier in identifiers)
                for machine_id, identifiers in self.mapper.nodes.items()}

    # methods on instances
    def running_identifiers(self) -> NameList:
        """ Return the identifiers of the Supervisor instances in RUNNING state. """
        return self.identifiers_by_states([SupvisorsInstanceStates.RUNNING])

    def isolated_identifiers(self) -> NameList:
        """ Return the identifiers of the Supervisors in ISOLATED state. """
        return self.identifiers_by_states([SupvisorsInstanceStates.ISOLATED])

    def valid_identifiers(self) -> NameList:
        """ Return the identifiers of the Supervisors NOT in ISOLATED state. """
        return self.identifiers_by_states([x for x in SupvisorsInstanceStates
                                           if x != SupvisorsInstanceStates.ISOLATED])

    def identifiers_by_states(self, states: List[SupvisorsInstanceStates]) -> NameList:
        """ Return the Supervisor identifiers sorted by Supervisor state. """
        return [identifier for identifier, status in self.instances.items()
                if status.state in states]

    def activate_checked(self) -> NameList:
        """ Once authorized, a Supvisors instance will be set to RUNNING only when it is certain it won't interfere
        with any sequencing in progress.

        :return: the identifiers of the checked Supvisors instances.
        """
        checked_identifiers: NameList = []
        for status in self.instances.values():
            if status.state == SupvisorsInstanceStates.CHECKED:
                status.state = SupvisorsInstanceStates.RUNNING
                self.export_status(status)
                checked_identifiers.append(status.identifier)
        return checked_identifiers

    def invalidate(self, status: SupvisorsInstanceStatus, fence=None) -> None:
        """ Declare the Supvisors instance STOPPED or ISOLATED, according to the auto_fence option.

        The local Supvisors instance is never set to ISOLATED, whatever the option is set or not.
        Always give it a chance to restart.

        This method is expected to be called only from CHECKING or FAILED state.

        :param status: the Supvisors instance to invalid.
        :param fence: True when the remote Supvisors instance has isolated the local Supvisors instance.
        """
        if status.identifier == self.local_identifier:
            # WARN: getting here would definitely be a bug
            #       anyway, the local Supvisors instance will NEVER be ISOLATED from itself
            self.logger.critical('Context.invalidate: local Supvisors instance is not operational')
            status.state = SupvisorsInstanceStates.STOPPED
        elif fence or (self.supvisors.options.auto_fence and self.state_modes.master_state in WORKING_STATES):
            # isolation of the remote Supvisors instance can be initiated when:
            #   - the remote Supvisors instance has isolated the local Supvisors instance (auth exchange)
            #   - the remote Supvisors instance has become non-responsive, and the option auto_fence is activated,
            #     the Supvisors FSM is in WORKING_STATES.
            status.state = SupvisorsInstanceStates.ISOLATED
        else:
            status.state = SupvisorsInstanceStates.STOPPED
        # publish SupvisorsInstanceStatus
        self.export_status(status)

    def invalidate_failed(self) -> Tuple[NameList, Set[ProcessStatus]]:
        """ Identify the Supvisors instances that cannot be reached anymore, and the processes that were running
        on them, so that they can eventually be re-distributed elsewhere.

        :return: the identifiers of the invalidated Supvisors instances and the processes in failure.
        """
        invalidated_identifiers: NameList = []
        failed_processes: Set[ProcessStatus] = set()
        for status in self.instances.values():
            if status.state == SupvisorsInstanceStates.FAILED:
                # invalid silent Supvisors instances
                self.invalidate(status)
                invalidated_identifiers.append(status.identifier)
                # for processes that were running on node, invalidate node in process
                # WARN: Decision is made NOT to remove the Supvisors instance from the ProcessStatus
                #       and NOT to remove the ProcessStatus from the Context if no more reference to it.
                #       The aim is to keep a trace in the Web UI about the application processes that have been lost
                #       and their related description.
                failed_processes.update({process for process in status.running_processes()
                                         if process.invalidate_identifier(status.identifier)})
        # trigger the corresponding Supvisors events
        self.publish_process_failures(failed_processes)
        #  return the identifiers of all invalidated Supvisors instances and the processes declared in failure
        return invalidated_identifiers, failed_processes

    def export_status(self, status: SupvisorsInstanceStatus) -> None:
        """ Publish SupvisorsInstanceStatus and SupvisorsStatus to Supvisors listeners. """
        if self.external_publisher:
            self.external_publisher.send_instance_status(status.serial())

    # methods on applications / processes
    def get_managed_applications(self) -> Dict[str, ApplicationStatus]:
        """ Get the managed applications (as defined in rules file).

        :return: the managed applications.
        """
        return {application_name: application for application_name, application in self.applications.items()
                if application.rules.managed}

    def is_namespec(self, namespec: str) -> bool:
        """ Check if the namespec is valid with the context.

        :return: True if the namespec is valid.
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

        :param namespec: the process namespec.
        :return: the corresponding ProcessStatus.
        """
        application_name, process_name = split_namespec(namespec)
        return self.applications[application_name].processes[process_name]

    def find_runnable_processes(self, regex: str) -> List[ProcessStatus]:
        """ Get all processes whose namespec matches the regex.
        The processes shall not be already running.

        :return: the candidate processes.
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

        :param application_name: the name of the application.
        :return: the application stored in the Supvisors context.
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

    def setdefault_process(self, identifier: str, info: Payload) -> Optional[ProcessStatus]:
        """ Return the process corresponding to info if found,
        otherwise load rules from the rules file, create a new process entry if rules exist and return it.
        Processes that are not defined in the rules files will not be stored in the Supvisors context.

        :param identifier: the identification of the Supvisors instance that sent this payload.
        :param info: the payload representing the process.
        :return: the process stored in the Supvisors context.
        """
        application_name, process_name = info['group'], info['name']
        namespec = make_namespec(application_name, info['name'])
        # get application
        application = self.setdefault_application(application_name)
        # search for existing process in application
        process = application.processes.get(process_name)
        new_process = process is None
        if new_process:
            # create process rules
            # by default, apply application starting / running failure strategies
            rules = ProcessRules(self.supvisors)
            rules.starting_failure_strategy = application.rules.starting_failure_strategy
            rules.running_failure_strategy = application.rules.running_failure_strategy
            if self.supvisors.parser:
                # load process rules from rules files
                self.supvisors.parser.load_program_rules(namespec, rules)
                self.logger.debug(f'Context.setdefault_process: namespec={namespec} rules={rules}')
            # create a new ProcessStatus
            process = ProcessStatus(application_name, info['name'], rules, self.supvisors)
        # store the payload in the ProcessStatus
        process.add_info(identifier, info)
        # add a new ProcessStatus to the ApplicationStatus
        if new_process:
            application.add_process(process)
        return process

    def load_processes(self, status: SupvisorsInstanceStatus, all_info: Optional[PayloadList],
                       check_state: bool = True) -> None:
        """ Load application dictionary from the process information received from the remote Supvisors.

        This is meant to happen only in CHECKING state.

        :param status: the Supvisors instance.
        :param all_info: the process information got from the node.
        :param check_state: set to True if CHECKING state should be verified.
        :return: None.
        """
        self.logger.trace(f'Context.load_processes: identifier={status.usage_identifier} all_info={all_info}')
        # get SupvisorsInstanceStatus corresponding to identifier
        if all_info is None:
            # the check call in SupervisorProxy failed
            # the remote Supvisors instance is likely starting, restarting or shutting down so defer
            self.logger.warn('Context.load_processes: failed to get all process info from'
                             f' Supvisors={status.usage_identifier}')
            # go back to STOPPED to give it a chance at next TICK
            status.state = SupvisorsInstanceStates.STOPPED
        elif not check_state or status.state == SupvisorsInstanceStates.CHECKING:
            # TODO: check process remote monotonic time vs CHECKING local time
            # store processes into their application entry
            for info in all_info:
                # get or create process
                process = self.setdefault_process(status.identifier, info)
                if process:
                    # share the instance to the Supervisor instance that holds it
                    status.add_process(process)
            # re-evaluate application sequences and status
            for application in self.applications.values():
                application.update_sequences()
                application.update()
        else:
            # may happen if CHECKING phase too long
            # (lots of Supvisors instances and local instance busy processing too many events)
            self.logger.debug(f'Context.load_processes: unexpected with non-CHECKING'
                              f' Supvisors={status.usage_identifier}')

    def publish_process_failures(self, failed_processes: Set[ProcessStatus]) -> None:
        """ Publish the Supvisors events related with the processes failures.

        :param failed_processes: the processes in failure.
        :return: None.
        """
        # publish process status in failure
        if self.external_publisher:
            for process in failed_processes:
                self.external_publisher.send_process_status(process.serial())
        # update all application sequences and status
        for application_name in {process.application_name for process in failed_processes}:
            application = self.applications[application_name]
            # the application sequences update is useless as long as the application.process map is not impacted
            # (see decision comment above in on_timer_event)
            # application.update_sequences()
            application.update()
            if self.external_publisher:
                self.external_publisher.send_application_status(application.serial())

    def check_process(self, status: SupvisorsInstanceStatus,
                      event: Payload, check_source=True) -> Optional[Tuple[ApplicationStatus, ProcessStatus]]:
        """ Check and return the internal data corresponding to the process event.

        :param status: the Supvisors instance from which the event has been received.
        :param event: the event payload.
        :param check_source: if True, the process should contain information related to the Supvisors instance.
        :return: None.
        """
        application_name, process_name = event['group'], event['name']
        try:
            application = self.applications[application_name]
            if process_name == '*':
                process = None
            else:
                process = application.processes[process_name]
                assert not check_source or status.identifier in process.info_map
            return application, process
        except (AssertionError, KeyError):
            # highly unexpected (process events missed somehow?)
            # that would point out a discrepancy between the local context and the remote context
            # as it has never been observed on target platforms so far, just log and ignore
            # NOTE: do NOT use the invalidate method to avoid an isolation, which is not required here
            namespec = make_namespec(application_name, process_name)
            self.logger.error(f'Context.check_process: ignoring event about unknown process={namespec}'
                              f' received from Supvisors={status.usage_identifier}')

    # methods on events
    def on_discovery_event(self, identifier: str, nick_identifier: str) -> None:
        """ Insert a new Supvisors instance if Supvisors is in discovery mode and the origin is unknown.

        If this event is received, the discovery mode is enabled.

        :param identifier: the remote Supvisors identifier.
        :param nick_identifier: the remote Supervisor identifier.
        :return: None.
        """
        if self.mapper.check_candidate(identifier, nick_identifier):
            # NOTE: use the first IP address in the list
            item = f'<{nick_identifier}>{identifier}'
            supvisors_id = self.mapper.add_instance(item)
            self.logger.info(f'Context.on_discovery_event: new SupvisorsInstanceId={supvisors_id}')
            real_identifier = supvisors_id.identifier
            self.instances[real_identifier] = SupvisorsInstanceStatus(supvisors_id, self.supvisors)
            self.state_modes.add_instance(real_identifier)

    def on_identification_event(self, event: Payload) -> None:
        """ Complete the remote Supvisors instance identification.

        :param event: The network information of the remote Supvisors instance.
        :return: None.
        """
        # only accepted if later than CHECKING date
        identifier, timestamp = event['identifier'], event['now_monotonic']
        status: SupvisorsInstanceStatus = self.instances[identifier]
        if status.is_checking(timestamp):
            self.mapper.identify(event)
        else:
            # may happen if CHECKING phase too long
            # (lots of Supvisors instances and local instance busy processing too many events)
            self.logger.debug(f'Context.on_identification_event: unexpected with Supvisors={status.usage_identifier}'
                              f' and timestamp={timestamp} (CHECKING at {status.checking_time})')

    def on_authorization(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ Method called upon reception of an authorization event telling if the remote Supvisors instance
        authorizes the local Supvisors instance to process its events.

        :param status: the Supvisors instance that sent the event.
        :param event: the Supvisors instance authorization status.
        :return: None.
        """
        auth_code, timestamp = event['authorization'], event['now_monotonic']
        try:
            authorization = AuthorizationTypes(auth_code)
        except ValueError:
            self.logger.error(f'SupervisorProxy.is_authorized: unknown AuthorizationTypes code={auth_code}')
            authorization = AuthorizationTypes.NOT_AUTHORIZED
        # check Supvisors instance state
        if not status.is_checking(timestamp):
            self.logger.error('Context.on_authorization: auth rejected from non-CHECKING'
                              f' Supvisors={status.usage_identifier} at timestamp={timestamp}')
            return None
        # process authorization status
        if authorization == AuthorizationTypes.UNKNOWN:
            # the check call in SupervisorProxy failed
            # the remote Supvisors instance is likely starting, restarting or shutting down so defer
            self.logger.warn('Context.on_authorization: failed to get auth status'
                             f' from Supvisors={status.usage_identifier}')
            # go back to STOPPED to give it a chance at next TICK
            status.state = SupvisorsInstanceStates.STOPPED
        elif authorization == AuthorizationTypes.NOT_AUTHORIZED:
            self.logger.warn('Context.on_authorization: the local Supvisors instance is isolated'
                             f' by Supvisors={status.usage_identifier}')
            self.invalidate(status, True)
        elif authorization == AuthorizationTypes.INCONSISTENT:
            self.logger.warn('Context.on_authorization: the local Supvisors configuration is inconsistent'
                             f' with the configuration of Supvisors={status.usage_identifier}')
            self.invalidate(status, True)
        else:
            self.logger.info(f'Context.on_authorization: the local Supvisors instance is authorized to work with'
                             f' Supvisors={status.usage_identifier}')
            status.state = SupvisorsInstanceStates.CHECKED

    def on_local_tick_event(self, event: Payload) -> None:
        """ Method called upon reception of a tick event from the local Supvisors instance.

        The method updates the times of the corresponding SupvisorsInstanceStatus and its ProcessStatus.
        Finally, the updated SupvisorsInstanceStatus is published.

        :param event: the TICK event sent.
        :return: None.
        """
        # for local Supvisors instance, repeat local data
        counter = event['sequence_counter']
        tick_mtime = event['when_monotonic']
        tick_time = event['when']
        self.local_status.update_tick(counter, tick_mtime, tick_time)
        # trigger hand-shake on first TICK received
        if self.local_status.state == SupvisorsInstanceStates.STOPPED:
            self.local_status.state = SupvisorsInstanceStates.CHECKING
            self.supvisors.rpc_handler.send_check_instance(self.local_identifier)
        # publish new Supvisors Instance status
        self.export_status(self.local_status)

    def on_tick_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ Method called upon reception of a tick event from the remote Supvisors instance, telling that it is active.

        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method also updates the times of the corresponding SupvisorsInstanceStatus and its ProcessStatus.
        Finally, the updated SupvisorsInstanceStatus is published.
        It is assumed that identifier validity has been checked before.

        :param status: the Supvisors instance from which the event has been received.
        :param event: the TICK event sent.
        :return: None.
        """
        # check if local tick has been received yet
        # NOTE: it is needed because remote ticks are tagged against last local tick received
        if self.local_status.state not in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            self.logger.debug('Context.on_tick_event: waiting for local tick first')
            return
        # for remote Supvisors instance, use local Supvisors instance data
        status.update_tick(event['sequence_counter'], event['when_monotonic'], event['when'],
                           self.local_sequence_counter)
        # trigger hand-shake on first TICK received
        if status.state == SupvisorsInstanceStates.STOPPED:
            status.state = SupvisorsInstanceStates.CHECKING
            self.supvisors.rpc_handler.send_check_instance(status.identifier)
        # publish new Supvisors Instance status
        self.export_status(status)

    def on_timer_event(self, event: Payload) -> None:
        """ Check that all Supvisors instances are still publishing.

        Supvisors considers that there a Supvisors instance is not active if no tick received in last 10s.

        :param event: The timer event.
        :return: The identifiers of the invalidated Supvisors instances and the processes in failure.
        """
        # use the local TICK counter received as a reference
        sequence_counter = event['sequence_counter']
        # check all Supvisors instances
        for status in self.instances.values():
            if status.is_inactive(sequence_counter):
                self.logger.warn(f'Context.on_timer_event: {status.usage_identifier} FAILED')
                status.state = SupvisorsInstanceStates.FAILED
                self.export_status(status)

    def on_instance_failure(self, status: SupvisorsInstanceStatus) -> None:
        """ Declare as FAILED a Supvisors instance that had an XML-RPC failure.

        :param status: The Supvisors instance that sent the event.
        :return: None.
        """
        # processes will be dealt in FAILED processing
        status.state = SupvisorsInstanceStates.FAILED
        self.export_status(status)

    def on_process_removed_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ Method called upon reception of a process removed event from the remote Supvisors instance.
        Following an XML-RPC update_numprocs, the size of homogeneous process groups may decrease and lead to removal
        of processes.
        A call to the XML-RPC removeProcessGroup triggers this event too.

        :param status: The Supvisors instance from which the event has been received.
        :param event: The event payload.
        :return: None.
        """
        # accept events only in CHECKED / RUNNING state
        if status.state in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            self.logger.debug(f'Context.on_remove_process_event: got event {event}'
                              f' from Supvisors={status.usage_identifier}')
            # get internal data
            app_proc = self.check_process(status, event)
            if app_proc:
                application_impacted = False
                # get process targets
                application, event_process = app_proc
                if event_process:
                    processes = [event_process]
                else:
                    processes = application.get_instance_processes(status.identifier)
                for process in processes:
                    # WARN: process_failures are not triggered here as the processes have been properly stopped
                    #  as a consequence of the user action
                    # In order to inform users on Supvisors event interface, a fake state DELETED (-1) is sent
                    process_event = event.copy()
                    process_event.update({'name': process.process_name, 'state': -1})
                    if self.external_publisher:
                        self.external_publisher.send_process_event(process_event)
                    # remove process from instance_status
                    status.remove_process(process)
                    # delete the process info entry related to the node
                    if process.remove_identifier(status.identifier):
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

    def on_process_disability_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ Method called upon reception of a process enabled event from the remote Supvisors instance.
        Following an XML-RPC enable/disable on a program, the corresponding process are allowed to be started or not.

        :param status: the Supvisors instance from which the event has been received
        :param event: the event payload
        :return: None
        """
        # accept events only in CHECKED / RUNNING state
        if status.state in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            self.logger.debug(f'Context.on_process_enabled_event: got event {event}'
                              f' from Supvisors={status.usage_identifier}')
            # get internal data
            app_proc = self.check_process(status, event)
            if app_proc:
                process = app_proc[1]
                # update the process info entry related to the node
                process.update_disability(status.identifier, event['disabled'])
                # at the moment, process disability has no impact on the application and process status
                # so only the process event publication makes sense
                if self.external_publisher:
                    self.external_publisher.send_process_event(event)

    def on_process_state_event(self, status: SupvisorsInstanceStatus, event: Payload) -> Optional[ProcessStatus]:
        """ Method called upon reception of a process event from the remote Supvisors instance.
        Supvisors checks that the handling of the event is valid in case of auto fencing.
        The method updates the ProcessStatus corresponding to the event, and thus the wrapping ApplicationStatus.
        Finally, the updated ProcessStatus and ApplicationStatus are published.

        :param status: the Supvisors instance from which the event has been received.
        :param event: the event payload.
        :return: None.
        """
        # accept events only in CHECKED / RUNNING state
        if status.state in [SupvisorsInstanceStates.CHECKED, SupvisorsInstanceStates.RUNNING]:
            self.logger.debug(f'Context.on_process_event: got event {event} from Supvisors={status.usage_identifier}')
            # WARN: the Master may send a process event corresponding to a process that is not configured in it
            forced_event = 'forced' in event
            app_proc = self.check_process(status, event, not forced_event)
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
                        # NOTE: use a copy so that the caller is not impacted by the payload change
                        event = event.copy()
                        event['state'] = process.displayed_state
                        del event['forced']
                else:
                    # update the ProcessStatus based on new information received from a local Supvisors instance
                    process.update_info(status.identifier, event)
                    try:
                        # update command line in Supervisor
                        self.supvisors.supervisor_data.update_extra_args(process.namespec, event['extra_args'])
                    except KeyError:
                        # process not found in Supervisor internal structure
                        self.logger.debug(f'Context.on_process_event: cannot apply extra args to {process.namespec}'
                                          ' unknown to local Supervisor')
                # forced event may be dismissed
                if updated:
                    # refresh internal status
                    status.update_process(process)
                    application.update()
                    # publish process event, status and application status
                    if self.external_publisher:
                        # timestamp the event in the local reference time
                        event['event_mtime'] = time.monotonic()
                        self.external_publisher.send_process_event(event)
                        self.external_publisher.send_process_status(process.serial())
                        self.external_publisher.send_application_status(application.serial())
                    return process
