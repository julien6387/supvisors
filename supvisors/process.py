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

from supervisor.options import make_namespec
from supervisor.states import RUNNING_STATES, STOPPED_STATES

from supvisors.ttypes import ProcessStates
from supvisors.utils import *


class ProcessRules(object):
    """ Defines the rules for starting a process, iaw deployment file.

    Attributes are:

        - the addresses where the process can be started (all by default),
        - the order in the starting sequence of the application,
        - the order in the stopping sequence of the application (not implemented yet),
        - a status telling if the process is required within the application,
        - a status telling if Supvisors has to wait for the process to exit before triggering the next phase in the starting sequence of the application,
        - the expected loading of the process on the considered hardware (can be anything at the user discretion: CPU, RAM, etc).
    """

    def __init__(self, supvisors):
        """ Initialization of the attributes. """
        # TODO: think about adding a period for tasks
        # period should be greater than startsecs
        # autorestart should be False
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['info_source', 'logger'])
        # attributes
        self.addresses = ['*']
        self.start_sequence = 0
        self.stop_sequence = 0
        self.required = False
        self.wait_exit = False
        self.expected_loading = 1

    def check_dependencies(self, namespec):
        """ Update rules after they have been read from the deployment file
        a required process that is not in the starting sequence is forced to optional
        If addresses are not defined, all addresses are applicable """
        # required MUST have start_sequence, so force to optional if no start_sequence
        if self.required and self.start_sequence == 0:
            self.logger.warn('{} - required forced to False because no start_sequence defined'.format(namespec))
            self.required = False
        # if no addresses, consider all addresses
        if not self.addresses:
            self.addresses = ['*']
            self.logger.warn('{} - no address defined so all Supvisors addresses are applicable'.format(namespec))

    def __str__(self):
        """ Contents as string """
        return 'addresses={} start_sequence={} stop_sequence={} required={} wait_exit={} loading={}'.format(self.addresses,
            self.start_sequence, self.stop_sequence, self.required, self.wait_exit, self.expected_loading)

    # serialization
    def serial(self):
        """ Return a serializable form of the ProcessRules """
        return {'addresses': self.addresses,
            'start_sequence': self.start_sequence, 'stop_sequence': self.stop_sequence,
            'required': self.required, 'wait_exit': self.wait_exit, 'expected_loading': self.expected_loading}


# ProcessStatus class
class ProcessStatus(object):
    """ Class defining the status of a process of Supvisors.

    Attributes:
    - the application name, or group name from a Supervisor point of view
    - the process name
    - the synthetic state of the process, same enumeration as Supervisor
    - a status telling if the process has exited expectantly
    - the date of the last event received
    - a mark to restart the process when it is stopped (used when address is lost or when using a restart conciliation strategy)
    - the list of all addresses where the process is running
    - a Supervisor-like process info dictionary for each address (running or not)
    - the starting rules related to this process
    - optional extra arguments to be passed to the command line
    - a status telling if the wait_exit rule is applicable (should be temporary). """

    def __init__(self, application_name, process_name, supvisors):
        """ Initialization of the attributes. """
        # keep a reference of the Supvisors data
        self.supvisors = supvisors
        supvisors_short_cuts(self, ['address_mapper', 'info_source', 'logger', 'options'])
        # attributes
        self.application_name = application_name
        self.process_name = process_name
        self._state = ProcessStates.UNKNOWN
        self.expected_exit = True
        self.last_event_time = 0
        self.mark_for_restart = False
        # expected one single applicable address
        self.addresses = set() # addresses
        self.infos = {} # address: processInfo
        # rules part
        self.rules = ProcessRules(supvisors)
        self.extra_args = ''
        self.ignore_wait_exit = False

    # access
    def namespec(self):
        """ Returns a namespec from application and process names """
        return make_namespec(self.application_name, self.process_name)

    def stopped(self):
        """ Return True if process is stopped, as designed in Supervisor """
        return self.state in STOPPED_STATES

    def running(self):
        """ Return True if process is running, as designed in Supervisor """
        return self.state in RUNNING_STATES

    def running_on(self, address):
        """ Return True if process is running on address """
        return self.running() and address in self.addresses

    def pid_running_on(self, address):
        """ Return True if process is RUNNING on address 
        Different from running_on as it considers only the RUNNING state and not STARTING or BACKOFF
        This is used by the statistics module that requires an existing PID """
        return self.state == ProcessStates.RUNNING and address in self.addresses

    def accept_extra_arguments(self):
        """ Return True if process rules are compatible with extra arguments. """
        return not self.info_source.autorestart(self.namespec())

    # property for state access
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, new_state):
        if self._state != new_state:
            self._state = new_state
            self.logger.info('Process {} is {} at {}'.format(self.namespec(), self.state_string(), list(self.addresses)))

    def conflicting(self):
        """ Return True if the process is in a conflicting state (more than one instance running) """
        return len(self.addresses) > 1

    # serialization
    def serial(self):
        """ Return a serializable form of the ProcessStatus """
        return {'application_name': self.application_name, 'process_name': self.process_name,
            'statecode': self.state, 'statename': self.state_string(),
            'expected_exit': self.expected_exit, 'last_event_time': self.last_event_time,
            'addresses': list(self.addresses)}

    # methods
    def state_string(self):
        """ Return the state as a string """
        return ProcessStates._to_string(self.state)

    def add_info(self, address, info):
        """ Insert a new Supervisor ProcessInfo in internal list """
        # init expected entry
        info['expected'] = not info['spawnerr']
        # remove useless fields
        self.filter(info)
        # store time info
        self.last_event_time = info['now']
        info['event_time'] = self.last_event_time
        self.update_single_times(info, self.last_event_time, int(time()))
        # add info entry to process
        self.logger.debug('adding {} for {}'.format(info, address))
        self.infos[address] = info
        # update process status
        self.update_status(address, info['state'], info['expected']) 
        # fix address rule
        if self.rules.addresses == ['#']:
            if self.address_mapper.addresses.index(address) == self.options.procnumbers[self.process_name]:
                self.rules.addresses = [address]
 
    def update_info(self, address, event):
        """ Update the internal ProcessInfo from event received """
        # do not add process in list while not added through tick
        if address in self.infos:
            info = self.infos[address]
            self.logger.trace('inserting {} into {} at {}'.format(event, info, address))
            new_state = event['state']
            info['state'] = new_state
            # manage times and pid
            remote_time = event['now']
            info['event_time'] = remote_time
            self.last_event_time = remote_time
            self.update_single_times(info, remote_time, int(time()))
            if new_state == ProcessStates.RUNNING:
                info['pid'] = event['pid']
                info['spawnerr'] = ''
            elif new_state in [ProcessStates.STARTING, ProcessStates.BACKOFF]:
                info['start'] = remote_time
                info['stop'] = 0
                info['uptime'] = 0
            elif new_state in STOPPED_STATES:
                info['stop'] = remote_time
                info['pid'] = 0
            # update expected entry
            info['expected'] = event['expected'] if new_state == ProcessStates.EXITED else True
            # update / check running addresses
            self.update_status(address, new_state, info['expected'])
            self.logger.debug('new processInfo: {}'.format(info))
        else:
            self.logger.warn('ProcessEvent rejected for {}. wait for tick from {}'.format(self.process_name, address))

    def update_times(self, address, remote_time, local_time):
        """ Update the time entries of the internal ProcessInfo when a new tick is received from the remote Supvisors instance """
        if address in self.infos:
            processInfo = self.infos[address]
            self.update_single_times(processInfo, remote_time, local_time)

    @staticmethod
    def update_single_times(info, remote_time, local_time):
        """ Update time entries of a Process info. """
        info['now'] = remote_time
        info['local_time'] = local_time
        info['uptime'] = (remote_time - info['start']) if info['state'] in [ProcessStates.RUNNING, ProcessStates.STOPPING] else 0

    def invalidate_address(self, address):
        """ Update status of a process that was running on a lost address """
        self.logger.debug('{} invalidateAddress {} / {}'.format(self.namespec(), self.addresses, address))
        # reassign the difference between current set and parameter
        if address in self.addresses:
            self.addresses.remove(address)
        if address in self.infos:
            # force process info to UNKNOWN at address
            self.infos[address]['state'] = ProcessStates.UNKNOWN
        # check if conflict still applicable
        if not self.evaluate_conflict():
            if len(self.addresses) == 1:
                # if only one address where process is running, the global state is the state of this process
                self.state = next(self.infos[address]['state'] for address in self.addresses)
            elif self.running():
                # addresses is empty for a running process. action expected to fix the inconsistency
                self.logger.warn('no more address for running process {}'.format(self.namespec()))
                self.state = ProcessStates.FATAL
                # mark process for restart only if autorestart is set in Supervisor's ProcessConfig
                self.mark_for_restart = self.info_source.autorestart(self.namespec())
            elif self.state == ProcessStates.STOPPING:
                # STOPPING is the last state received before the address is lost. consider STOPPED now
                self.state = ProcessStates.STOPPED
        else:
            self.logger.debug('process {} still in conflict after address invalidation'.format(self.namespec()))

    def update_status(self, address, new_state, expected):
        """ Updates the state and list of running address iaw the new event. """
        # update addresses list
        if new_state in STOPPED_STATES:
            self.addresses.discard(address)
        elif new_state in RUNNING_STATES:
            # replace if current state stopped-like, add otherwise
            if self.stopped():
                self.addresses = {address}
                # reset autorestart flag as it becomes useless
                self.mark_for_restart = False
            else:
                self.addresses.add(address)
        # evaluate state iaw running addresses
        if not self.evaluate_conflict():
            # if zero element, state is the state of the program addressed
            if self.addresses:
                self.state = next(self.infos[address]['state'] for address in self.addresses)
                self.expected_exit = True
            else:
                self.state = new_state
                self.expected_exit = expected

    def evaluate_conflict(self):
        """ Gets a synthetic state if several processes are in a RUNNING-like state. """
        if self.conflicting():
            # several processes seems to be in a running state so that becomes tricky
            states = {self.infos[address]['state'] for address in self.addresses}
            self.logger.debug('{} multiple states {} for addresses {}'.format(self.process_name,
                [ProcessStates._to_string(x) for x in states], list(self.addresses)))
            # state synthesis done using the sorting of RUNNING_STATES
            self.state = self.running_state(states)
            return True

    @staticmethod
    def filter(info):
        """ Remove from dictionary the fields that are not used in Supvisors and/or not updated through process events """
        for key in ProcessStatus._Filters:
            info.pop(key, None)

    @staticmethod
    def running_state(states):
        """ Return the first matching state in RUNNING_STATES """
        return next((state for state in RUNNING_STATES if state in states), ProcessStates.UNKNOWN)

    # list of removed entries in process info dictionary
    _Filters = ['statename', 'description', 'stderr_logfile', 'stdout_logfile', 'logfile', 'exitstatus']
