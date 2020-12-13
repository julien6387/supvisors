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

from supervisor.options import make_namespec
from supervisor.rpcinterface import SupervisorNamespaceRPCInterface
from supervisor.states import RUNNING_STATES, STOPPED_STATES

from supvisors.ttypes import ProcessStates, RunningFailureStrategies
from supvisors.utils import *


class ProcessRules(object):
    """ Defines the rules for starting a process, iaw rules file.

    Attributes are:

        - addresses: the addresses where the process can be started
            (all by default),
        - start_sequence: the order in the starting sequence of the application,
        - stop_sequence: the order in the stopping sequence of the application,
        - required: a status telling if the process is required within the
            application,
        - wait_exit: a status telling if Supvisors has to wait for the process
            to exit before triggering the next phase in the starting sequence
            of the application,
        - expected_loading: the expected loading of the process on the
            considered hardware (can be anything at the user discretion: CPU,
            RAM, etc),
        - running_failure_strategy: supersedes the application rule and defines
            the strategy to apply when the process crashes when the application
            is running.
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # TODO: think about adding a period for tasks
        # period should be greater than startsecs
        # autorestart should be False
        # keep a reference to the Supvisors data
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['info_source', 'logger'])
        # attributes
        self.addresses = ['*']
        self.start_sequence = 0
        self.stop_sequence = 0
        self.required = False
        self.wait_exit = False
        self.expected_loading = 1
        self.running_failure_strategy = RunningFailureStrategies.CONTINUE

    def check_dependencies(self, namespec):
        """ Update rules after they have been read from the rules file.

        A required process that is not in the starting sequence is forced to
        optional.
        If addresses are not defined, all addresses are applicable.
        Supervisor autorestart is not compatible with RunningFailureStrategy
        STOP / RESTART.
        """
        # required MUST have start_sequence, so force to optional if
        # start_sequence is not set
        if self.required and self.start_sequence == 0:
            self.logger.warn('{} - required forced to False because'
                             ' no start_sequence defined'.format(namespec))
            self.required = False
        # if no addresses, consider all addresses
        if not self.addresses:
            self.addresses = ['*']
            self.logger.warn('{} - no address defined so all Supvisors'
                             ' addresses are applicable'.format(namespec))
        # disable autorestart when RunningFailureStrategies is not CONTINUE
        if self.running_failure_strategy != RunningFailureStrategies.CONTINUE:
            if self.info_source.autorestart(namespec):
                self.info_source.disable_autorestart(namespec)
                self.logger.warn('{} - autorestart disabled due to running failure strategy {}'
                                 .format(namespec,
                                         RunningFailureStrategies.to_string(self.running_failure_strategy)))

    def __str__(self):
        """ Contents as string. """
        return 'addresses={} start_sequence={} stop_sequence={} required={}' \
               ' wait_exit={} expected_loading={} running_failure_strategy={}'. \
            format(self.addresses,
                   self.start_sequence, self.stop_sequence, self.required,
                   self.wait_exit, self.expected_loading,
                   RunningFailureStrategies.to_string(self.running_failure_strategy))

    # serialization
    def serial(self):
        """ Return a serializable form of the ProcessRules. """
        return {'addresses': self.addresses,
                'start_sequence': self.start_sequence,
                'stop_sequence': self.stop_sequence,
                'required': self.required,
                'wait_exit': self.wait_exit,
                'expected_loading': self.expected_loading,
                'running_failure_strategy':
                    RunningFailureStrategies.to_string(self.running_failure_strategy)}


class ProcessStatus(object):
    """ Class defining the status of a process of Supvisors.

    Attributes are:

        - application_name: the application name, or group name from a
            Supervisor point of view,
        - process_name: the process name,
        - state: the synthetic state of the process, same enumeration as
            Supervisor,
        - expected_exit: a status telling if the process has exited expectantly,
        - last_event_time: the local date of the last information received,
        - extra_args: the additional arguments passed to the command line,
        - addresses: the list of all addresses where the process is running,
        - infos: a process info dictionary for each address (running or not),
        - rules: the rules related to this process.
    """

    def __init__(self, application_name, process_name, supvisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        supvisors_shortcuts(self, ['address_mapper', 'info_source',
                                   'logger', 'options'])
        # copy Supervisor method to self
        ProcessStatus.update_description = SupervisorNamespaceRPCInterface._interpretProcessInfo
        # attributes
        self.application_name = application_name
        self.process_name = process_name
        self._state = ProcessStates.UNKNOWN
        self.expected_exit = True
        self.last_event_time = 0
        self._extra_args = ''
        # expected one single applicable address
        self.addresses = set()  # addresses
        self.infos = {}  # address: processInfo
        # rules part
        self.rules = ProcessRules(supvisors)

    # property for state access
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if self._state != new_state:
            self._state = new_state

    # property for extra_args access
    @property
    def extra_args(self):
        return self._extra_args

    @extra_args.setter
    def extra_args(self, new_args):
        if self._extra_args != new_args:
            self._extra_args = new_args
            self.info_source.update_extra_args(self.namespec(), new_args)

    # serialization
    def serial(self):
        """ Return a serializable form of the ProcessStatus. """
        return {'application_name': self.application_name,
                'process_name': self.process_name,
                'statecode': self.state,
                'statename': self.state_string(),
                'expected_exit': self.expected_exit,
                'last_event_time': self.last_event_time,
                'addresses': list(self.addresses),
                'extra_args': self.extra_args}

    # access
    def namespec(self):
        """ Returns a namespec from application and process names. """
        return make_namespec(self.application_name, self.process_name)

    def crashed(self):
        """ Return True if process has crashed or has exited unexpectedly. """
        return (self.state == ProcessStates.FATAL or
                (self.state == ProcessStates.EXITED and not self.expected_exit))

    def stopped(self):
        """ Return True if process is stopped, as designed in Supervisor. """
        return self.state in STOPPED_STATES

    def running(self):
        """ Return True if process is running, as designed in Supervisor. """
        return self.state in RUNNING_STATES

    def running_on(self, address):
        """ Return True if process is running on address. """
        return self.running() and address in self.addresses

    def pid_running_on(self, address):
        """ Return True if process is RUNNING on address.
        Different from running_on as it considers only the RUNNING state and
        not STARTING or BACKOFF.
        This is used by the statistics module that requires an existing PID. """
        return self.state == ProcessStates.RUNNING and address in self.addresses

    def conflicting(self):
        """ Return True if the process is in a conflicting state (more than one
        instance running). """
        return len(self.addresses) > 1

    # methods
    def state_string(self):
        """ Return the state as a string. """
        return ProcessStates.to_string(self.state)

    def add_info(self, address, process_info):
        """ Insert a new process information in internal list.
        process_info is a subset of the dict received from Supervisor.getProcessInfo.
        it contains the attributes declared in supvisors.utils.__Payload_Keys.
        """
        # keep date of last information received
        # use local time here as there is no guarantee that addresses will be time synchonized
        self.last_event_time = int(time())
        # store information
        info = self.infos[address] = process_info
        info['local_time'] = self.last_event_time
        self.update_uptime(info)
        self.logger.debug('adding {} at {}'.format(info, address))
        # reset extra_args
        info['extra_args'] = ''
        self.extra_args = ''
        # update process status
        self.update_status(address, info['state'], info['expected'])
        # fix address rule
        if self.rules.addresses == ['#']:
            if self.address_mapper.addresses.index(address) == \
                    self.options.procnumbers[self.process_name]:
                self.rules.addresses = [address]

    def update_info(self, address, payload):
        """ Update the internal process information with event payload. """
        # do not consider process event while not added through tick
        if address in self.infos:
            # keep date of last information received
            # use local time here as there is no guarantee that addresses will be time synchonized
            self.last_event_time = int(time())
            # last received extra_args are always applicable
            self.extra_args = payload['extra_args']
            # refresh internal information
            info = self.infos[address]
            info['local_time'] = self.last_event_time
            self.logger.trace('inserting {} into {} at {}'.format(payload, info, address))
            info.update(payload)
            # re-evaluate description using Supervisor function
            info['description'] = self.update_description(info)
            # reset start time if process in a starting state
            new_state = info['state']
            if new_state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                info['start'] = info['now']
            if new_state in STOPPED_STATES:
                info['stop'] = info['now']
            self.update_uptime(info)
            # update / check running addresses
            self.update_status(address, new_state, info['expected'])
            self.logger.debug('new process info: {}'.format(info))
        else:
            self.logger.warn('ProcessEvent rejected for {}.'
                             ' wait for tick from {}'.format(self.process_name, address))

    def update_times(self, address, remote_time):
        """ Update the internal process information when
        a new tick is received from the remote Supvisors instance. """
        if address in self.infos:
            info = self.infos[address]
            info['now'] = remote_time
            self.update_uptime(info)
            # it may have an impact on the description depending on the process state
            info['description'] = self.update_description(info)

    @staticmethod
    def update_uptime(info):
        """ Update uptime entry of a process information. """
        info['uptime'] = (info['now'] - info['start']) \
            if info['state'] in [ProcessStates.RUNNING, ProcessStates.STOPPING] \
            else 0

    def invalidate_address(self, address, is_master):
        """ Update status of a process that was running on a lost address. """
        self.logger.debug('{} invalidateAddress {} / {}'.format(
            self.namespec(), self.addresses, address))
        # reassign the difference between current set and parameter
        if address in self.addresses:
            self.addresses.remove(address)
        if address in self.infos:
            # force process info to UNKNOWN at address
            self.infos[address]['state'] = ProcessStates.UNKNOWN
        # check if conflict still applicable
        if not self.evaluate_conflict():
            if len(self.addresses) == 1:
                # if process is running on only one address,
                # the global state is the state of this process
                self.state = next(self.infos[address]['state']
                                  for address in self.addresses)
            elif self.running():
                # addresses is empty for a running process
                # action expected to fix the inconsistency
                self.logger.warn('no more address for running process {}'
                                 .format(self.namespec()))
                self.state = ProcessStates.FATAL
                # notify the failure to dedicated handler, only if local
                # address is master
                if is_master:
                    self.supvisors.failure_handler.add_default_job(self)
            elif self.state == ProcessStates.STOPPING:
                # STOPPING is the last state received before the address is lost
                # consider STOPPED now
                self.state = ProcessStates.STOPPED
        else:
            self.logger.debug('process {} still in conflict after address invalidation'
                              .format(self.namespec()))

    def update_status(self, address, new_state, expected):
        """ Updates the state and list of running address iaw the new event. """
        # update addresses list
        if new_state in STOPPED_STATES:
            self.addresses.discard(address)
        elif new_state in RUNNING_STATES:
            # replace if current state stopped-like, add otherwise
            if self.stopped():
                self.addresses = {address}
            else:
                self.addresses.add(address)
        # evaluate state iaw running addresses
        if not self.evaluate_conflict():
            # if zero element, state is the state of the program addressed
            if self.addresses:
                self.state = next(self.infos[address]['state']
                                  for address in self.addresses)
                self.expected_exit = True
            else:
                self.state = new_state
                self.expected_exit = expected
        # log the new status
        log_trace = 'Process {} is {}'.format(self.namespec(), self.state_string())
        if self.addresses:
            log_trace += ' on {}'.format(list(self.addresses))
        self.logger.info(log_trace)

    def evaluate_conflict(self):
        """ Gets a synthetic state if several processes are in a RUNNING-like state. """
        if self.conflicting():
            # several processes seems to be in a running state
            # so that becomes tricky
            states = {self.infos[address]['state']
                      for address in self.addresses}
            self.logger.debug('{} multiple states {} for addresses {}'
                              .format(self.process_name,
                                      [ProcessStates.to_string(x) for x in states],
                                      list(self.addresses)))
            # state synthesis done using the sorting of RUNNING_STATES
            self.state = self.running_state(states)
            return True

    @staticmethod
    def running_state(states):
        """ Return the first matching state in RUNNING_STATES. """
        return next((state for state in RUNNING_STATES if state in states),
                    ProcessStates.UNKNOWN)
