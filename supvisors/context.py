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

from supvisors.external_com.eventinterface import EventPublisherInterface
from .application import ApplicationRules, ApplicationStatus
from .instancestatus import SupvisorsInstanceStatus
from .process import ProcessRules, ProcessStatus
from .ttypes import (ApplicationStates, SupvisorsInstanceStates, SupvisorsStates,
                     WORKING_STATES, CLOSING_STATES,
                     Ipv4Address, NameList, Payload, PayloadList, LoadMap)


class Context:
    """ The Context class holds the main data of Supvisors.

    Attributes are:
        - supvisors: the Supvisors global structure ;
        - instances: the dictionary of all SupvisorsInstanceStatus (key is Supvisors identifier) ;
        - applications: the dictionary of all ApplicationStatus (key is application name) ;
        - start_date: the date since Supvisors entered the INITIALIZATION state ;
        - last_state_modes: the last Supvisors State and Modes published.
    """

    # annotation types
    InstancesMap = Dict[str, SupvisorsInstanceStatus]
    ApplicationsMap = Dict[str, ApplicationStatus]

    # attributes
    supvisors: Any = None
    start_date: float = 0.0
    instances: InstancesMap = None
    applications: ApplicationsMap = None
    last_state_modes: Payload = None

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        # the Supvisors instances declared statically
        self.instances = {identifier: SupvisorsInstanceStatus(supvisors_id, supvisors)
                          for identifier, supvisors_id in self.supvisors.mapper.instances.items()}
        # the applications known to Supvisors
        self.applications = {}

    def reset(self) -> None:
        """ Reset the context to prepare a new synchronization phase.

        :return: None
        """
        self.local_status.state_modes.master_identifier = ''
        self.start_date = time.monotonic()
        for status in self.instances.values():
            status.reset()

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    @property
    def external_publisher(self) -> Optional[EventPublisherInterface]:
        """ Get the Supvisors external publisher. """
        return self.supvisors.external_publisher

    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.supvisors.mapper.local_identifier

    @property
    def local_status(self) -> SupvisorsInstanceStatus:
        """ Get the local Supvisors instance structure. """
        return self.instances[self.local_identifier]

    @property
    def local_sequence_counter(self) -> int:
        """ Get last local TICK sequence counter, used for node invalidation. """
        return self.local_status.sequence_counter

    # Master operations
    @property
    def master_identifier(self) -> str:
        """ Get the identifier of the Supvisors Master instance. """
        return self.local_status.state_modes.master_identifier

    @master_identifier.setter
    def master_identifier(self, identifier: str) -> None:
        """ Set the identifier of the known Supvisors Master instance. """
        self.logger.info(f'Context.master_identifier: {identifier}')
        self.publish_state_modes({'master_identifier': identifier})

    @property
    def is_master(self) -> bool:
        """ Return True if the local Supvisors instance is the Supvisors Master instance. """
        return self.master_identifier == self.local_identifier

    @property
    def master_instance(self) -> Optional[SupvisorsInstanceStatus]:
        """ Get local Supvisors instance structure. """
        return self.instances.get(self.master_identifier)

    @property
    def supvisors_state(self) -> Optional[SupvisorsStates]:
        """ Get the supvisors state of the Supvisors Master instance. """
        if self.master_instance:
            return self.master_instance.state_modes.state
        return None

    def elect_master(self, running_identifiers: Optional[NameList] = None) -> None:
        """ Select the Master Supvisors instance among the possible candidates. """
        if not running_identifiers:
            running_identifiers = self.running_identifiers()
        self.logger.info(f'Context.elect_master: Supvisors Master instance election among {running_identifiers}')
        if running_identifiers:
            # elect master instance among working instances only if not fixed before
            # of course, master instance must be running
            self.logger.debug(f'Context.elect_master: master_identifier={self.master_identifier}')
            if not self.master_identifier or self.master_identifier not in running_identifiers:
                # choose Master among the core instances because they are expected to be more stable
                #   this logic is kept independently of CORE being selected as synchro_options
                core_identifiers = self.supvisors.mapper.core_identifiers
                self.logger.debug(f'Context.elect_master: core_identifiers={core_identifiers}')
                if core_identifiers:
                    running_core_identifiers = set(running_identifiers).intersection(core_identifiers)
                    if running_core_identifiers:
                        running_identifiers = running_core_identifiers
                # arbitrarily choice: master instance has the 'lowest' nick_identifier among running instances
                self.master_identifier = min(running_identifiers,
                                             key=lambda x: self.supvisors.mapper.instances[x].nick_identifier)

    # States and Modes
    def publish_state_modes(self, event: Payload) -> None:
        """ Publish the Supvisors instance state and modes.
        FIXME: it's not only publication but update too

        This information is provided internally by the local Supvisors instance, and it will be published to all
        connected Supvisors instances.

        :param event: the state or the mode updated.
        :return: None.
        """
        # keys are Starter, Stopper, fsm_state
        # internal update due to FSM state change or Starter / Stopper progress change
        changed, state_modes = self.local_status.apply_state_modes(event)
        if changed:
            # on change, publish the local Supvisors state and modes to the other Supvisors instances
            self.supvisors.rpc_handler.send_state_event(state_modes.serial())
            # publish SupvisorsInstanceStatus and SupvisorsStatus
            self.export_status(self.local_status)

    def get_state_modes(self) -> Payload:
        """ Get the Supvisors state and modes, based on all connected Supvisors instances.
        Supvisors state is the FSM state and is a reflection of the Supvisors Master instance state.
        Supvisors modes consist in the existence of starting or stopping jobs across all connected Supvisors instances.

        :return: the Supvisors state and the identifiers of the Supvisors instances having starting or stopping jobs
        """
        payload = self.local_status.state_modes.serial()
        # overwrite starting_jobs and starting_jobs based on a synthesis from all Supvisors instances
        starting, stopping = [], []
        for identifier, status in self.instances.items():
            if status.state_modes.starting_jobs:
                starting.append(identifier)
            if status.state_modes.stopping_jobs:
                stopping.append(identifier)
        # update the payload
        # NOTE: discovery mode is only based on the local Supvisors instance
        #       there's no chance that Supvisors instances in discovery mode would communicate with Supvisors instances
        #       that are NOT in discovery mode
        payload.update({'starting_jobs': starting, 'stopping_jobs': stopping})
        return payload

    def _publish_state_mode(self) -> None:
        """ Publish the new state and modes if it differs from the latest publication.

        :return: None
        """
        current_state_modes = self.get_state_modes()
        if self.last_state_modes != current_state_modes:
            self.last_state_modes = current_state_modes
            self.external_publisher.send_supvisors_status(current_state_modes)

    def export_status(self, status: SupvisorsInstanceStatus) -> None:
        """ Publish SupvisorsInstanceStatus and SupvisorsStatus to Supvisors listeners. """
        if self.external_publisher:
            self.external_publisher.send_instance_status(status.serial())
            self._publish_state_mode()

    # methods on nodes
    def is_valid(self, identifier: str, nick_identifier: str,
                 ipv4_address: Ipv4Address) -> Optional[SupvisorsInstanceStatus]:
        """ Check the validity of the message emitter.
        Validity is ok if the identifier is known with the correct IP address and not declared isolated. """
        ip_address, http_port = ipv4_address
        identifiers = self.supvisors.mapper.filter([identifier, nick_identifier])
        if len(identifiers) != 1:
            # multiple resolution not expected here
            return None
        status = self.instances[identifiers[0]]
        if (not status.isolated and ip_address in status.supvisors_id.ip_addresses
                and status.supvisors_id.http_port == http_port):
            return status
        return None

    def get_nodes_load(self) -> LoadMap:
        """ Get the Supvisors instances load grouped by node.

        :return: The nodes load
        """
        return {ip_address: sum(self.instances[identifier].get_load()
                                for identifier in identifiers)
                for ip_address, identifiers in self.supvisors.mapper.nodes.items()}

    # methods on instances
    def initial_running(self) -> bool:
        """ Return True if all Supervisor instances are in RUNNING state. """
        return all(status.state == SupvisorsInstanceStates.RUNNING
                   for identifier, status in self.instances.items()
                   if identifier in self.supvisors.mapper.initial_identifiers)

    def all_running(self) -> bool:
        """ Return True if all Supervisor instances are in RUNNING state. """
        return all(status.state == SupvisorsInstanceStates.RUNNING
                   for status in self.instances.values())

    def running_identifiers(self) -> NameList:
        """ Return the identifiers of the Supervisor instances in RUNNING state. """
        return self.instances_by_states([SupvisorsInstanceStates.RUNNING])

    def running_core_identifiers(self) -> bool:
        """ Check if core SupvisorsInstanceStatus are in RUNNING state.

        :return: True if all core SupvisorsInstanceStatus are in RUNNING state
        """
        core_identifiers = self.supvisors.mapper.core_identifiers
        if core_identifiers:
            return all(status.state == SupvisorsInstanceStates.RUNNING
                       for identifier, status in self.instances.items()
                       if identifier in core_identifiers)
        return False

    def isolated_instances(self) -> NameList:
        """ Return the identifiers of the Supervisors in ISOLATED state. """
        return self.instances_by_states([SupvisorsInstanceStates.ISOLATED])

    def valid_instances(self) -> NameList:
        """ Return the identifiers of the Supervisors NOT in ISOLATED state. """
        return self.instances_by_states([SupvisorsInstanceStates.UNKNOWN,
                                         SupvisorsInstanceStates.CHECKING, SupvisorsInstanceStates.CHECKED,
                                         SupvisorsInstanceStates.RUNNING, SupvisorsInstanceStates.SILENT])

    def instances_by_states(self, states: List[SupvisorsInstanceStates]) -> NameList:
        """ Return the Supervisor identifiers sorted by Supervisor state. """
        return [identifier for identifier, status in self.instances.items() if status.state in states]

    def activate_checked(self):
        """ Once authorized, a Supvisors instance will be set to RUNNING only when it is certain it won't interfere
        with any sequencing in progress. """
        for status in self.instances.values():
            if status.state == SupvisorsInstanceStates.CHECKED:
                status.state = SupvisorsInstanceStates.RUNNING

    def invalid_unknown(self):
        """ This can be triggered by the FSM when TIMEOUT is set in synchro_options.
        After the synchro_timeout has passed, all UNKNOWN Supvisors instances are invalidated. """
        for status in self.instances.values():
            if status.state == SupvisorsInstanceStates.UNKNOWN:
                # nothing to do on processes as none received yet
                self.invalid(status)

    def invalid(self, status: SupvisorsInstanceStatus, fence=None) -> None:
        """ Declare SILENT or ISOLATED the SupvisorsInstanceStatus in parameter, according to the auto_fence option.

        The local Supvisors instance is never set to ISOLATED, whatever the option is set or not.
        Always give it a chance to restart.

        :param status: the Supvisors instance to invalid.
        :param fence: True when the remote Supvisors instance has isolated the local Supvisors instance.
        """
        if status.identifier == self.local_identifier:
            # A very few events can cause this situation:
            # 1. a network failure (XML-RPC request)
            # 2. a discrepancy has been detected between the internal context and the process events received
            #    a new CHECKING phase is required
            # NOTE: the local Supvisors instance cannot be ISOLATED from itself
            self.logger.critical('Context.invalid: local Supvisors instance is either SILENT or inconsistent')
            status.state = SupvisorsInstanceStates.SILENT
        elif fence or (self.supvisors.options.auto_fence and self.supvisors_state in WORKING_STATES):
            # isolation of the remote Supvisors instance can be initiated when:
            #   - the remote Supvisors instance has isolated the local Supvisors instance (auth exchange)
            #   - the remote Supvisors instance has become non-responsive, and the option auto_fence is activated,
            #     the Supvisors FSM is in WORKING_STATES.
            status.state = SupvisorsInstanceStates.ISOLATED
        else:
            status.state = SupvisorsInstanceStates.SILENT
        # publish SupvisorsInstanceStatus and SupvisorsStatus
        self.export_status(status)

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

    def load_processes(self, status: SupvisorsInstanceStatus, all_info: Optional[PayloadList]) -> None:
        """ Load application dictionary from the process information received from the remote Supvisors.

        :param status: the Supvisors instance.
        :param all_info: the process information got from the node.
        :return: None.
        """
        self.logger.trace(f'Context.load_processes: identifier={status.usage_identifier} all_info={all_info}')
        # get SupvisorsInstanceStatus corresponding to identifier
        if all_info is None:
            # the check call in SupervisorProxy failed
            # the remote Supvisors instance is likely starting, restarting or shutting down so defer
            self.logger.warn('Context.load_processes: failed to get all process info from'
                             f' Supvisors={status.usage_identifier}')
            # go back to UNKNOWN to give it a chance at next TICK
            status.state = SupvisorsInstanceStates.UNKNOWN
        else:
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

    # methods on events
    def on_instance_state_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ Update the Supvisors instance state and modes.

        :param status: the Supvisors instance that sent the event.
        :param event: the new state and modes.
        :return: None.
        """
        # ISOLATED instances are not updated anymore
        # should not happen as the subscriber should have been disconnected but there may be a tick in the pipe
        if not status.isolated:
            # update the Supvisors instance StateModes status
            status.update_state_modes(event)
            # check if a Master is known to this Supvisors instance and compare with the local's
            # this is considered only if the remote Supvisors instance is not about to restart or shut down
            remote_master = status.state_modes.master_identifier
            if remote_master and status.state_modes.state not in CLOSING_STATES:
                if not self.master_identifier:
                    # the local Supvisors instance doesn't know about a master yet but remote Supvisors instance does
                    # it typically happens when the local Supervisor instance has just been started whereas a Supvisors
                    # group was already operating, so accept the remote perception
                    self.logger.warn(f'Context.on_instance_state_event: accept Master={remote_master}'
                                     f' declared by Supvisors={status.usage_identifier}')
                    self.master_identifier = remote_master
                elif remote_master != self.master_identifier:
                    # ALERT: 2 different perceptions of the master, likely due to a split-brain situation.
                    self.logger.warn('Context.on_instance_state_event: Master conflict. '
                                     f' Local declares Master={self.master_identifier}'
                                     f' - Supvisors={status.usage_identifier} declares Master={remote_master}')
                    # WARN: resetting the Master at local level isn't enough because there may be multiple Supvisors
                    #   instances having different perceptions, and they are still publishing at their own pace.
                    #   So in order to avoid infinite Master conflict, adjudication is made using the same principle
                    #   as the Master selection. This is expected to converge more quickly.
                    candidates = [remote_master, self.master_identifier]
                    self.master_identifier = ''
                    self.elect_master(candidates)
            # publish the new Instance status and Supvisors synthesis
            self.export_status(status)

    def on_authorization(self, status: SupvisorsInstanceStatus, authorized: Optional[bool]) -> bool:
        """ Method called upon reception of an authorization event telling if the remote Supvisors instance
        authorizes the local Supvisors instance to process its events.

        :param status: the Supvisors instance that sent the event.
        :param authorized: the Supvisors instance authorization status.
        :return: True if authorized both ways.
        """
        # check Supvisors instance state
        if status.state != SupvisorsInstanceStates.CHECKING:
            self.logger.error('Context.on_authorization: auth rejected from non-CHECKING'
                              f' Supvisors={status.usage_identifier}')
            return False
        # process authorization status
        if authorized is None:
            # the check call in SupervisorProxy failed
            # the remote Supvisors instance is likely starting, restarting or shutting down so defer
            self.logger.warn('Context.on_authorization: failed to get auth status'
                             f' from Supvisors={status.usage_identifier}')
            # go back to UNKNOWN to give it a chance at next TICK
            status.state = SupvisorsInstanceStates.UNKNOWN
        elif not authorized:
            self.logger.warn('Context.on_authorization: the local Supvisors instance is isolated'
                             f' by Supvisors={status.usage_identifier}')
            self.invalid(status, True)
        else:
            self.logger.info(f'Context.on_authorization: local Supvisors instance is authorized to work with'
                             f' Supvisors={status.usage_identifier}')
            status.state = SupvisorsInstanceStates.CHECKED
            return True
        return False

    def on_local_tick_event(self, event: Payload) -> None:
        """ Method called upon reception of a tick event from the local Supvisors instance.
        The method updates the times of the corresponding SupvisorsInstanceStatus and its ProcessStatus.
        Finally, the updated SupvisorsInstanceStatus is published.

        :param event: the TICK event sent
        :return: None
        """
        # for local Supvisors instance, repeat local data
        counter = event['sequence_counter']
        tick_mtime = event['when_monotonic']
        tick_time = event['when']
        self.local_status.update_tick(counter, tick_mtime, tick_time)
        # trigger hand-shake on first TICK received
        if self.local_status.state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.SILENT]:
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
        # ISOLATED instances are not updated anymore
        if not status.isolated:
            # update the Supvisors instance with the TICK event
            self.supvisors.mapper.assign_stereotypes(status.identifier, event['stereotypes'])
            # for remote Supvisors instance, use local Supvisors instance data
            status.update_tick(event['sequence_counter'], event['when_monotonic'], event['when'],
                               self.local_sequence_counter)
            # trigger hand-shake on first TICK received
            if status.state in [SupvisorsInstanceStates.UNKNOWN, SupvisorsInstanceStates.SILENT]:
                status.state = SupvisorsInstanceStates.CHECKING
                self.supvisors.rpc_handler.send_check_instance(status.identifier)
            # publish new Supvisors Instance status
            self.export_status(status)

    def on_discovery_event(self, identifier: str, nick_identifier: str) -> bool:
        """ Insert a new Supvisors instance if Supvisors is in discovery mode and the origin is unknown.
        If this event is received, the discovery mode is enabled.

        :param identifier: the remote Supvisors identifier.
        :param nick_identifier: the remote Supervisor identifier.
        :return: True if a new Supvisors instance has been inserted.
        """
        if self.supvisors.mapper.check_candidate(identifier, nick_identifier):
            # NOTE: use the first IP address in the list
            item = f'<{nick_identifier}>{identifier}'
            supvisors_id = self.supvisors.mapper.add_instance(item)
            self.logger.info(f'SupvisorsMapper.on_discovery_event: new SupvisorsInstanceId={supvisors_id}')
            self.instances[supvisors_id.identifier] = SupvisorsInstanceStatus(supvisors_id, self.supvisors)
            return True
        return False

    def on_timer_event(self, event: Payload) -> Tuple[NameList, Set[ProcessStatus]]:
        """ Check that all Supvisors instances are still publishing.
        Supvisors considers that there a Supvisors instance is not active if no tick received in last 10s.

        :param event: the timer event.
        :return: the identifiers of the invalidated Supvisors instances and the processes in failure.
        """
        invalidated_identifiers: List[str] = []
        failed_processes: Set[ProcessStatus] = set()
        # use the local TICK counter received as a reference
        sequence_counter = event['sequence_counter']
        # check all Supvisors instances
        for status in self.instances.values():
            if status.is_inactive(sequence_counter):
                # invalid silent Supvisors instances
                self.invalid(status)
                invalidated_identifiers.append(status.identifier)
                # for processes that were running on node, invalidate node in process
                # WARN: Decision is made NOT to remove the node payload from the ProcessStatus and NOT to remove
                #       the ProcessStatus from the Context if no more node payload left.
                #       The aim is to keep a trace in the Web UI about the application processes that have been lost
                #       and their related description.
                failed_processes.update({process for process in status.running_processes()
                                         if process.invalidate_identifier(status.identifier)})
        # trigger the corresponding Supvisors events
        self.publish_process_failures(failed_processes)
        #  return the identifiers of all invalidated Supvisors instances and the processes declared in failure
        return invalidated_identifiers, failed_processes

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

    def on_instance_failure(self, status: SupvisorsInstanceStatus) -> Set[ProcessStatus]:
        """ Invalid a Supvisors instance that had an XML-RPC failure.

        :param status: the Supvisors instance that sent the event.
        :return: the identifiers of the invalidated Supvisors instances and the processes in failure.
        """
        failed_processes: Set[ProcessStatus] = set()
        # invalid silent Supvisors instances
        self.invalid(status)
        # for processes that were running on node, invalidate node in process
        failed_processes.update({process for process in status.running_processes()
                                 if process.invalidate_identifier(status.identifier)})
        # trigger the corresponding Supvisors events
        self.publish_process_failures(failed_processes)
        return failed_processes

    def check_process(self, status: SupvisorsInstanceStatus,
                      event: Payload, check_source=True) -> Optional[Tuple[ApplicationStatus, ProcessStatus]]:
        """ Check and return the internal data corresponding to the process event.

        :param status: the Supvisors instance from which the event has been received
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
                assert not check_source or status.identifier in process.info_map
            return application, process
        except (AssertionError, KeyError):
            namespec = make_namespec(application_name, process_name)
            # if the event is received during a Supvisors closing state, it can be ignored
            # otherwise, it means that there's a discrepancy in the internal context, which requires CHECKING
            if self.supvisors.fsm.state in CLOSING_STATES:
                self.logger.warn(f'Context.check_process: ignoring unknown event about process={namespec}'
                                 f' received from Supvisors={status.usage_identifier} while in'
                                 f' {self.supvisors.fsm.state} state')
            else:
                self.logger.error(f'Context.check_process: CHECKING required due to unknown event about'
                                  f' process={namespec} received from Supvisors={status.usage_identifier}')
                self.invalid(status)

    def on_process_removed_event(self, status: SupvisorsInstanceStatus, event: Payload) -> None:
        """ Method called upon reception of a process removed event from the remote Supvisors instance.
        Following an XML-RPC update_numprocs, the size of homogeneous process groups may decrease and lead to removal
        of processes.
        A call to the XML-RPC removeProcessGroup triggers this event too.

        :param status: the Supvisors instance from which the event has been received.
        :param event: the event payload.
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
                processes = [event_process] if event_process else application.get_instance_processes(status.identifier)
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
                        self.external_publisher.send_process_event(event)
                        self.external_publisher.send_process_status(process.serial())
                        self.external_publisher.send_application_status(application.serial())
                    return process
