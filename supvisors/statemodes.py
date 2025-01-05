# ======================================================================
# Copyright 2024 Julien LE CLEACH
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

import time
from typing import Any, Dict, Optional

from supervisor.loggers import Logger

from .external_com.eventinterface import EventPublisherInterface
from .internal_com.mapper import SupvisorsMapper, SupvisorsInstanceId
from .ttypes import SupvisorsStates, SupvisorsInstanceStates, NameSet, Payload


class StateModes:
    """ The Supvisors state and modes, as seen by a Supvisors instance.

    Attributes are:
        * identifier: the identifier of the Supvisors instance.
        * state: the FSM state.
        * degraded_mode: True if Supvisors is degraded (essential instance missing).
        * discovery_mode: True if the Supvisors discovery mode is enabled.
        * master_identifier: the identifier of the Supvisors Master instance.
        * starting_jobs: True if the Starter has jobs in progress.
        * stopping_jobs: True if the Stopper has jobs in progress.
        * instance_states: the SupvisorsInstanceStates synthesis.
    """

    STABLE_STATES = [SupvisorsInstanceStates.RUNNING,
                     SupvisorsInstanceStates.STOPPED,
                     SupvisorsInstanceStates.ISOLATED]

    def __init__(self, sup_id: SupvisorsInstanceId):
        """ Initialization of the attributes. """
        self.supvisors_id: SupvisorsInstanceId = sup_id
        self.state: SupvisorsStates = SupvisorsStates.OFF
        self.degraded_mode: bool = False
        self.discovery_mode: bool = False
        self.master_identifier: str = ''
        self.starting_jobs: bool = False
        self.stopping_jobs: bool = False
        self.instance_states: Dict[str, SupvisorsInstanceStates] = {}

    @property
    def identifier(self):
        """ Property getter for the 'identifier' attribute of the Supvisors instance. """
        return self.supvisors_id.identifier

    @property
    def nick_identifier(self):
        """ Property getter for the 'nick_identifier' attribute of the Supvisors instance. """
        return self.supvisors_id.nick_identifier

    def get_stable_identifiers(self) -> NameSet:
        """ Check the context stability of the Supvisors instance, by returning all its known remote Supvisors instances
        that are in a stable state (RUNNING, STOPPED, ISOLATED).

        In the event where any remote Supvisors instance is NOT in a stable state, the method returns an empty set.

        :return: the Supvisors identifiers if the context is completely stable.
        """
        stable_identifiers = set()
        for identifier, state in self.instance_states.items():
            if state not in StateModes.STABLE_STATES:
                return set()
            stable_identifiers.add(identifier)
        return stable_identifiers

    def running_identifiers(self) -> NameSet:
        """ Return the Supvisors instances seen as RUNNING. """
        return {identifier for identifier, state in self.instance_states.items()
                if state == SupvisorsInstanceStates.RUNNING}

    def update(self, payload: Payload) -> None:
        """ Get the Supvisors instance state and modes with changes applied.

        :param payload: the Supvisors instance state and modes.
        :return: None.
        """
        self.state = SupvisorsStates(payload['fsm_statecode'])
        self.degraded_mode = payload['degraded_mode']
        self.discovery_mode = payload['discovery_mode']
        self.master_identifier = payload['master_identifier']
        self.starting_jobs = payload['starting_jobs']
        self.stopping_jobs = payload['stopping_jobs']
        self.instance_states = {identifier: SupvisorsInstanceStates[state_name]
                                for identifier, state_name in payload['instance_states'].items()}

    def serial(self):
        """ Return a serializable form of the StatesModes. """
        return {'identifier': self.identifier,
                'nick_identifier': self.nick_identifier,
                'now_monotonic': time.monotonic(),
                'fsm_statecode': self.state.value, 'fsm_statename': self.state.name,
                'degraded_mode': self.degraded_mode,
                'discovery_mode': self.discovery_mode,
                'master_identifier': self.master_identifier,
                'starting_jobs': self.starting_jobs,
                'stopping_jobs': self.stopping_jobs,
                'instance_states': {identifier: state.name
                                    for identifier, state in self.instance_states.items()}}


# annotation types
StateModesMap = Dict[str, StateModes]


class SupvisorsStateModes:
    """ The Supvisors global state & modes.

    This structure holds references to the state and modes declared by every Supvisors instance.

    A few considerations about Master selection:
        - the Master must be unique,
        - the Master must be seen as RUNNING by the local Supvisors instance,
        - the Master must be declared RUNNING by all the remote Supvisors instances seen as RUNNING
          by the local Supvisors instance.
    """

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes. """
        self.supvisors = supvisors
        # get the reference to every Supvisors instance state & modes structure
        # NOTE: the content of this structure is fully driven by the Context instance,
        #       based on the declared Supvisors instances and the discovered ones
        self.instance_state_modes: StateModesMap = {identifier: StateModes(sup_id)
                                                    for identifier, sup_id in supvisors.mapper.instances.items()}
        # fill the local instance to initiate the first publication / other instances will be filled by notification
        self.local_state_modes.instance_states = {identifier: SupvisorsInstanceStates.STOPPED
                                                  for identifier in supvisors.mapper.instances}
        # even if no instance is declared, the local Supvisors instance is always configured
        self.discovery_mode: bool = supvisors.options.discovery_mode
        # the identifiers of the stable Supvisors instances (dynamic context)
        self.stable_identifiers: NameSet = set()

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
    def external_publisher(self) -> Optional[EventPublisherInterface]:
        """ Get the Supvisors external publisher. """
        return self.supvisors.external_publisher

    # Easy access
    @property
    def local_identifier(self) -> str:
        """ Get the local Supvisors instance identifier. """
        return self.mapper.local_identifier

    @property
    def local_state_modes(self) -> StateModes:
        """ Get the Supvisors state and modes of the local Supvisors instance. """
        return self.instance_state_modes[self.local_identifier]

    @property
    def master_state_modes(self) -> Optional[StateModes]:
        """ Get the Supvisors state and modes of the local Supvisors instance. """
        return self.instance_state_modes.get(self.master_identifier)

    @property
    def starting_identifiers(self):
        """ Return the list of Supvisors instances where starting jobs are in progress. """
        return [identifier for identifier, state_modes in self.instance_state_modes.items()
                if state_modes.starting_jobs]

    @property
    def stopping_identifiers(self):
        """ Return the list of Supvisors instances where stopping jobs are in progress. """
        return [identifier for identifier, state_modes in self.instance_state_modes.items()
                if state_modes.stopping_jobs]

    @property
    def master_state(self) -> Optional[SupvisorsStates]:
        """ Get the Supvisors state of the Supvisors Master instance. """
        master_state_modes = self.master_state_modes
        return master_state_modes.state if master_state_modes else None

    @property
    def state(self) -> SupvisorsStates:
        """ Get the FSM state of Supvisors, as seen by the local instance. """
        return self.local_state_modes.state

    @state.setter
    def state(self, fsm_state: SupvisorsStates) -> None:
        """ Get the Supvisors FSM state, as seen by the local instance. """
        if self.local_state_modes.state != fsm_state:
            self.logger.warn(f'SupvisorsStateModes.state: {fsm_state.name}')
            self.local_state_modes.state = fsm_state
            self.publish_status()

    @property
    def degraded_mode(self) -> bool:
        """ Return True if the Supvisors in running in a degraded context,
        i.e. any expected Supvisors instance is missing. """
        return self.local_state_modes.degraded_mode

    @degraded_mode.setter
    def degraded_mode(self, mode: bool) -> None:
        """ Set the degraded mode on the Supvisors local instance. """
        if self.local_state_modes.degraded_mode != mode:
            self.logger.debug(f'SupvisorsStateModes.mode: {mode}')
            self.local_state_modes.degraded_mode = mode
            self.publish_status()

    @property
    def discovery_mode(self) -> bool:
        """ Return True if the discovery mode is activated on the local instance. """
        return self.local_state_modes.discovery_mode

    @discovery_mode.setter
    def discovery_mode(self, mode: bool) -> None:
        """ Set the discovery mode on the Supvisors local instance.
        This attribute is set at start-up and not expected to change afterward. """
        self.local_state_modes.discovery_mode = mode

    @property
    def master_identifier(self) -> str:
        """ Get the identifier of the Supvisors Master instance. """
        return self.local_state_modes.master_identifier

    @master_identifier.setter
    def master_identifier(self, identifier: str) -> None:
        """ Set the identifier of the known Supvisors Master instance. """
        if self.local_state_modes.master_identifier != identifier:
            self.logger.warn(f'SupvisorsStateModes.master_identifier: {identifier}')
            self.local_state_modes.master_identifier = identifier
            self.publish_status()

    @property
    def starting_jobs(self) -> bool:
        """ Get the local starting jobs progress. """
        return self.local_state_modes.starting_jobs

    @starting_jobs.setter
    def starting_jobs(self, in_progress: bool) -> None:
        """ Update the local starting jobs progress and publish the new state and modes. """
        if self.local_state_modes.starting_jobs != in_progress:
            self.local_state_modes.starting_jobs = in_progress
            self.publish_status()

    @property
    def stopping_jobs(self) -> bool:
        """ Get the local stopping jobs progress. """
        return self.local_state_modes.stopping_jobs

    @stopping_jobs.setter
    def stopping_jobs(self, in_progress: bool) -> None:
        """ Update the local stopping jobs progress and publish the new state and modes. """
        if self.local_state_modes.stopping_jobs != in_progress:
            self.local_state_modes.stopping_jobs = in_progress
            self.publish_status()

    # Supvisors instance update
    def add_instance(self, identifier: str) -> None:
        """ Add a new discovered instance to the internal dictionary. """
        sup_id: SupvisorsInstanceId = self.supvisors.mapper.instances[identifier]
        self.instance_state_modes[identifier] = StateModes(sup_id)
        self.local_state_modes.instance_states[identifier] = SupvisorsInstanceStates.STOPPED

    def update_instance_state(self, identifier: str, new_state: SupvisorsInstanceStates) -> None:
        """ Update the state of the Supvisors instance.

        :param identifier: the identifier of the Supvisors instance.
        :param new_state: the new state of the Supvisors instance.
        :return: None.
        """
        self.local_state_modes.instance_states[identifier] = new_state
        if new_state in [SupvisorsInstanceStates.STOPPED, SupvisorsInstanceStates.ISOLATED]:
            # local identifier is unlikely unless there's a bug
            if identifier != self.local_identifier:
                self.logger.debug(f'SupvisorsStateModes.update_instance_state: reset Supvisors={identifier}')
                supvisors_id = self.instance_state_modes[identifier].supvisors_id
                self.instance_state_modes[identifier] = StateModes(supvisors_id)
        # if Master is not RUNNING anymore, a new election is required
        if new_state != SupvisorsInstanceStates.RUNNING and identifier == self.master_identifier:
            self.master_identifier = ''
        else:
            # avoid double publication
            self.publish_status()

    # Global update from a notification
    def on_instance_state_event(self, identifier: str, event: Payload):
        """ The event is fired on change by the remote Supvisors instance. """
        # ignore if sent by the local Supvisors instance because information may be lost in the gap
        if identifier != self.local_identifier:
            self.instance_state_modes[identifier].update(event)
            # export the Supvisors status because starting / stopping identifiers may have changed
            self.export_status()

    # Data publication and export
    def serial(self) -> Payload:
        """ The global view is based on the local instance view. """
        payload = self.local_state_modes.serial()
        # replace the local Starter/Stopper progress by the identifiers having starting/stopping jobs
        payload.update({'starting_jobs': self.starting_identifiers,
                        'stopping_jobs': self.stopping_identifiers})
        return payload

    def publish_status(self) -> None:
        """ Publish the local Supvisors state and modes to the other Supvisors instances. """
        self.supvisors.rpc_handler.send_state_event(self.local_state_modes.serial())
        # always export any change on self status
        self.export_status()

    def export_status(self) -> None:
        """ External publication to Supvisors listeners. """
        if self.external_publisher:
            self.external_publisher.send_supvisors_status(self.serial())

    # Master selection
    def is_running(self, identifier: str) -> bool:
        """ Return True if the local Supvisors instance sees the Supvisors instance as RUNNING. """
        return self.local_state_modes.instance_states[identifier] == SupvisorsInstanceStates.RUNNING

    def is_stable(self) -> bool:
        """ Return True if the Supvisors context is stable. """
        # TBC: add condition all in same FSM state ?
        return len(self.stable_identifiers) > 0

    def evaluate_stability(self) -> None:
        """ Evaluate the Supvisors stability, i.e. if all stable identifiers are identical for all Supvisors instances.

        This is called periodically from the Supvisors FSM.

        NOTE: a stable Supvisors instance is not necessarily RUNNING.
        """
        stable_identifiers = [sm.get_stable_identifiers()
                              for identifier, sm in self.instance_state_modes.items()
                              if self.is_running(identifier)]
        self.logger.debug(f'SupvisorsStateModes.update_stability: stable_identifiers={stable_identifiers}')
        if stable_identifiers and all(identifiers == stable_identifiers[0]
                                      for identifiers in stable_identifiers):
            # TBC: store only running ones ?
            self.stable_identifiers = stable_identifiers[0]
        else:
            self.stable_identifiers = set()
        self.logger.debug(f'SupvisorsStateModes.update_stability: stable_identifiers={self.stable_identifiers}')

    def get_master_identifiers(self) -> NameSet:
        """ Return the Master identifiers declared among the Supvisors instances seen as RUNNING.

        In the Supvisors OPERATION state, there should be exactly one.
        The 'no master' case may happen at Supvisors startup or in the event where the Supvisors Master is stopped.
        The 'multiple masters' case is a consequence of a split-brain situation.

        This method must be called only in a stable Supvisors context, otherwise there is no guarantee
        that the Supvisors Master instance seen locally as RUNNING is considered similarly in remote instances.

        :return: the Master identifiers.
        """
        # it could return directly a set but useful to debug
        all_masters = {identifier: sm.master_identifier
                       for identifier, sm in self.instance_state_modes.items()
                       if self.is_running(identifier)}
        self.logger.debug(f'SupvisorsStateModes.get_master_identifiers: all_masters={all_masters}')
        # NOTE: keep the empty string in the set because having one Master identifier and the empty string is a no-go
        return set(all_masters.values())

    def check_master(self, election: bool = True) -> bool:
        """ Return True if a unique RUNNING Supvisors instance is considered as a Master by all Supvisors instances
        in a stable context.

        :param election: add more logs when not in ELECTION state.
        :return: True if one Master.
        """
        masters: NameSet = self.get_master_identifiers()
        self.logger.debug(f'SupvisorsStateModes.check_master: masters={masters}')
        # masters cannot be empty
        if '' in masters:
            if not election:
                self.logger.warn('SupvisorsStateModes.check_master: at least one Supvisors instance has no Master')
            return False
        if len(masters) > 1:
            if not election:
                self.logger.warn('SupvisorsStateModes.check_master: multiple Supvisors Master instances found')
            return False
        return True

    def select_master(self) -> None:
        """ Select the Master Supvisors instance among the possible candidates.

        This method is called from a situation where there is either no master, or is it not running,
        or there are multiple master instances declared over all the Supvisors instances.
        In all cases, the context is fully stable, i.e. all Supvisors instances have a common perception of the other
        Supvisors instances.

        This method can also be called upon Supvisors user initiative to end the synchronization phase.

        A first priority is given to a Supvisors Master that is already declared by another Supvisors instance.
        A second priority is given to the Supvisors Core instances (as configured).
        Finally, a third priority is given to the 'lowest' nick_identifier.
        """
        # priority is given to existing Master instances if already identified
        all_candidates = self.get_master_identifiers()
        all_candidates.discard('')
        if not all_candidates:
            # no Master identified, so get the running instances
            all_candidates = self.local_state_modes.running_identifiers()
        # NOTE: choose Master among the core instances because they are expected to be more stable
        #       this logic is applied regardless of CORE being selected as synchro_options
        core_candidates = [identifier for identifier in self.mapper.core_identifiers
                           if identifier in all_candidates]
        self.logger.debug(f'SupvisorsStateModes.select_master: core_candidates={core_candidates}')
        candidates = core_candidates or all_candidates
        self.logger.debug(f'SupvisorsStateModes.select_master: candidates={candidates}')
        # arbitrarily choice: master instance has the 'lowest' nick_identifier among running instances
        self.master_identifier = min(candidates, key=lambda x: self.mapper.instances[x].nick_identifier)

    def accept_master(self) -> None:
        """ Accept a Master Supvisors instance if any is already selected by a remote Supvisors instance.

        This method is called from the SYNCHRONIZATION state, and is applicable when the USER option is set.
        The Supvisors user may unblock the SYNCHRONIZATION phase by selecting a Master instance from the Web UI
        or using the XML-RPC API.
        """
        masters: NameSet = self.get_master_identifiers()
        masters.discard('')
        self.logger.debug(f'SupvisorsStateModes.accept_master: masters={masters}')
        if masters:
            # arbitrarily choice: pick up the first one
            # if there's a conflict, il will be solved in ELECTION state
            # the important thing is to exit the SYNCHRONIZATION state if a USER Master is available
            self.master_identifier = next(iter(masters))

    # Core instances
    def core_instances_running(self) -> bool:
        """ Check if all Supvisors Core instances are in RUNNING state.

        This is checked against the stable identifiers to ensure that the Supvisors Core instances are seen as RUNNING
        by all Supvisors instances.
        That's why this method is not in Supvisors Context module.

        :return: True if all Supvisors Core instances are in RUNNING state.
        """
        core_identifiers = set(self.mapper.core_identifiers)
        stable_running_identifiers = {identifier for identifier in self.stable_identifiers
                                      if self.is_running(identifier)}
        return core_identifiers.issubset(stable_running_identifiers)
