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

import os

from typing import Dict, Union

from supervisor.http import NOT_DONE_YET
from supervisor.loggers import Logger, LevelsByName, LevelsByDescription, getLevelNumByDescription
from supervisor.options import make_namespec, split_namespec
from supervisor.xmlrpc import Faults, RPCError

from .application import ApplicationStatus
from .strategy import conciliate_conflicts
from .ttypes import (ApplicationStates, ConciliationStrategies, StartingStrategies, SupvisorsStates,
                     EnumClassType, EnumType)
from .utils import extract_process_info


# get Supvisors version from file
here = os.path.abspath(os.path.dirname(__file__))
version_txt = os.path.join(here, 'version.txt')
with open(version_txt, 'r') as ver:
    API_VERSION = ver.read().split('=')[1].strip()


class RPCInterface(object):
    """ This class holds the XML-RPC extension provided by **Supvisors**. """

    # type for any enumeration RPC parameter
    EnumParameterType = Union[str, int]

    def __init__(self, supvisors):
        """ Initialization of the attributes.

        :param supvisors: the global Supvisors structure
        """
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger

    # RPC Status methods
    def get_api_version(self):
        """ Return the version of the RPC API used by **Supvisors**.

        *@return* ``str``: the version id.
        """
        return API_VERSION

    def get_supvisors_state(self):
        """ Return the state of **Supvisors**.

        *@return* ``dict``: the state of **Supvisors** as an integer and a string.
        """
        return self.supvisors.fsm.serial()

    def get_master_address(self):
        """ Get the address of the **Supvisors** Master.

        *@return* ``str``: the IPv4 address or host name.
        """
        return self.supvisors.context.master_node_name

    def get_strategies(self):
        """ Get the default strategies applied by **Supvisors**:

            * auto-fencing: node isolation if it becomes inactive,
            * starting: used in the ``DEPLOYMENT`` state to start applications,
            * conciliation: used in the ``CONCILIATION`` state to conciliate conflicts.

        *@return* ``dict``: a structure containing data about the strategies applied.
        """
        options = self.supvisors.options
        return {'auto-fencing': options.auto_fence,
                'starting': options.starting_strategy.name,
                'conciliation': options.conciliation_strategy.name}

    def get_all_addresses_info(self):
        """ Get information about all **Supvisors** instances.

        *@return* ``list(dict)``: a list of structures containing data about all **Supvisors** instances.
        """
        return [self.get_address_info(node_name)
                for node_name in sorted(self.supvisors.context.nodes.keys())]

    def get_address_info(self, node_name):
        """ Get information about the **Supvisors** instance running on the host named node.

        *@param* ``str node_name``: the node where the Supervisor daemon is running.

        *@throws* ``RPCError``: with code ``Faults.BAD_ADDRESS`` if node is unknown to **Supvisors**.

        *@return* ``dict``: a structure containing data about the **Supvisors** instance.
        """
        try:
            status = self.supvisors.context.nodes[node_name]
        except KeyError:
            raise RPCError(Faults.BAD_ADDRESS, 'node {} unknown to Supvisors'.format(node_name))
        return status.serial()

    def get_all_applications_info(self):
        """ Get information about all applications managed in **Supvisors**.

        *@throws* ``RPCError``: with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
        ``INITIALIZATION`` state.

        *@return* ``list(dict)``: a list of structures containing data about all applications.
        """
        self._check_from_deployment()
        return [self.get_application_info(application_name)
                for application_name in self.supvisors.context.applications.keys()]

    def get_application_info(self, application_name):
        """ Get information about an application named application_name.

        *@param* ``str application_name``: the name of the application.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state,
            * with code ``Faults.BAD_NAME`` if application_name is unknown to **Supvisors**.

        *@return* ``dict``: a structure containing data about the application.
        """
        self._check_from_deployment()
        return self._get_application(application_name).serial()

    def get_application_rules(self, application_name):
        """ Get the rules used to start / stop the application named application_name.

        *@param* ``str application_name``: the name of the application.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state,
            * with code ``Faults.BAD_NAME`` if application_name is unknown to **Supvisors**.

        *@return* ``list(dict)``: a list of structures containing the rules.
        """
        self._check_from_deployment()
        result = self._get_application(application_name).rules.serial()
        result.update({'application_name': application_name})
        return result

    def get_all_process_info(self):
        """ Get synthetic information about all processes.

        *@throws* ``RPCError``: with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
        ``INITIALIZATION`` state,

        *@return* ``list(dict)``: a list of structures containing data about the processes.
        """
        self._check_from_deployment()
        return [process.serial()
                for application in self.supvisors.context.applications.values()
                for process in application.processes.values()]

    def get_process_info(self, namespec):
        """ Get synthetic information about a process named namespec.
        It gives a synthetic status, based on the process information coming from all the nodes where **Supvisors**
        is running.

        *@param* ``str namespec``: the process namespec (``name``, ``group:name``, or ``group:*``).

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state,
            * with code ``Faults.BAD_NAME`` if namespec is unknown to **Supvisors**.

        *@return* ``list(dict)``: a list of structures containing data about the processes.
        """
        self._check_from_deployment()
        application, process = self._get_application_process(namespec)
        if process:
            return [process.serial()]
        return [proc.serial() for proc in application.processes.values()]

    def get_all_local_process_info(self):
        """ Get information about all processes located on this node.
        It is a subset of ``supervisor.getProcessInfo``, used by **Supvisors** in INITIALIZATION state,
        and giving the extra arguments of the process.

        *@return* ``list(dict)``: a list of structures containing data about the processes.
        """
        supervisor_intf = self.supvisors.info_source.supervisor_rpc_interface
        all_info = supervisor_intf.getAllProcessInfo()
        return [self._get_local_info(info) for info in all_info]

    def get_local_process_info(self, namespec):
        """ Get local information about a process named namespec.
        It is a subset of ``supervisor.getProcessInfo``, used by **Supvisors** in INITIALIZATION state,
        and giving the extra arguments of the process.

        *@param* ``str namespec``: the process namespec (``name``, ``group:name``).

        *@throws* ``RPCError`` with code ``Faults.BAD_NAME`` if namespec is unknown to **Supvisors**.

        *@return* ``dict``: a structure containing data about the process.
        """
        supervisor_intf = self.supvisors.info_source.supervisor_rpc_interface
        info = supervisor_intf.getProcessInfo(namespec)
        return self._get_local_info(info)

    def get_process_rules(self, namespec):
        """ Get the rules used to start / stop the process named namespec.

        *@param* ``str namespec``: the process namespec (``name``, ``group:name``, or ``group:*``).

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state,
            * with code ``Faults.BAD_NAME`` if namespec is unknown to **Supvisors**.

        *@return* ``list(dict)``: a list of structures containing the rules.
        """
        self._check_from_deployment()
        application, process = self._get_application_process(namespec)
        if process:
            return [self._get_internal_process_rules(process)]
        return [self._get_internal_process_rules(proc) for proc in application.processes.values()]

    def get_conflicts(self):
        """ Get the conflicting processes among the managed applications.

        *@throws* ``RPCError``: with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
        ``INITIALIZATION`` state,

        *@return* ``list(dict)``: a list of structures containing data about the conflicting processes.
        """
        self._check_from_deployment()
        return [process.serial() for process in self.supvisors.context.conflicts()]

    # RPC Command methods
    def start_application(self, strategy: EnumParameterType, application_name, wait=True):
        """ Start the application named application_name iaw the strategy and the rules file.

        *@param* ``StartingStrategies strategy``: the strategy used to choose nodes, as a string or as a value.

        *@param* ``str application_name``: the name of the application.

        *@param* ``bool wait``: wait for the application to be fully started.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION``,
            * with code ``Faults.BAD_STRATEGY`` if strategy is unknown to **Supvisors**,
            * with code ``Faults.BAD_NAME`` if application_name is unknown to **Supvisors**,
            * with code ``Faults.ALREADY_STARTED`` if application is ``STARTING``, ``STOPPING`` or ``RUNNING``,
            * with code ``Faults.ABNORMAL_TERMINATION`` if application could not be started.

        *@return* ``bool``: always ``True`` unless error or nothing to start.
        """
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check application is known
        if application_name not in self.supvisors.context.applications.keys():
            raise RPCError(Faults.BAD_NAME, application_name)
        # check application is not already RUNNING
        application = self.supvisors.context.applications[application_name]
        if application.state != ApplicationStates.STOPPED:
            raise RPCError(Faults.ALREADY_STARTED, application_name)
        # TODO: develop a predictive model to check if starting can be achieved
        # if impossible due to a lack of resources, second try without optional
        # return false if still impossible
        done = self.supvisors.starter.start_application(strategy_enum, application)
        self.logger.debug('RPCInterface.start_application: {} done={}'.format(application_name, done))
        # wait until application fully RUNNING or (failed)
        if wait and not done:
            def onwait():
                # check starter
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                if application.state != ApplicationStates.RUNNING:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, application_name)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        # if done is True, nothing to do (no starting or impossible to start)
        return not done

    def stop_application(self, application_name, wait=True):
        """ Stop the application named application_name.

        *@param* ``str application_name``: the name of the application.

        *@param* ``bool wait``: wait for the application to be fully stopped.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`
              or ``CONCILIATION``,
            * with code ``Faults.BAD_NAME`` if application_name is unknown to **Supvisors**.
            * with code ``Faults.NOT_RUNNING`` if application is ``STOPPED``,

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_operating_conciliation()
        # check application is known
        if application_name not in self.supvisors.context.applications.keys():
            raise RPCError(Faults.BAD_NAME, application_name)
        # check application is not already STOPPED
        application = self.supvisors.context.applications[application_name]
        if not application.has_running_processes():
            raise RPCError(Faults.NOT_RUNNING, application_name)
        # stop the application
        done = self.supvisors.stopper.stop_application(application)
        self.logger.debug('RPCInterface.stop_application: {} done={}'.format(application_name, done))
        # wait until application fully STOPPED
        if wait and not done:
            def onwait():
                # check stopper
                if self.supvisors.stopper.in_progress():
                    return NOT_DONE_YET
                if application.state != ApplicationStates.STOPPED:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, application_name)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        # if done is True, nothing to do
        return not done

    def restart_application(self, strategy: EnumParameterType, application_name, wait=True):
        """ Restart the application named application_name iaw the strategy and the rules file.

        *@param* ``StartingStrategies strategy``: the strategy used to choose nodes, as a string or as a value.

        *@param* ``str application_name``: the name of the application.

        *@param* ``bool wait``: wait for the application to be fully restarted.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION``,
            * with code ``Faults.BAD_STRATEGY`` if strategy is unknown to **Supvisors**,
            * with code ``Faults.BAD_NAME`` if application_name is unknown to **Supvisors**,
            * with code ``Faults.ABNORMAL_TERMINATION`` if application could not be restarted.

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_operating()

        def onwait():
            # first wait for application to be stopped
            if onwait.waitstop:
                # job may be a boolean value if stop_application has nothing
                # to do
                value = type(onwait.job) is bool or onwait.job()
                if value is True:
                    # done. request start application
                    onwait.waitstop = False
                    value = self.start_application(strategy, application_name, wait)
                    if type(value) is bool:
                        return value
                    # deferred job to wait for application to be started
                    onwait.job = value
                return NOT_DONE_YET
            return onwait.job()

        onwait.delay = 0.5
        onwait.waitstop = True
        # request stop application. job is for deferred result
        onwait.job = self.stop_application(application_name, True)
        return onwait  # deferred

    def start_args(self, namespec, extra_args='', wait=True):
        """ Start a process on the local node.
        The behaviour is different from ``supervisor.startProcess`` as it sets the process state to ``FATAL``
        instead of throwing an exception to the RPC client.
        This RPC makes it also possible to pass extra arguments to the program command line.

        *@param* ``str namespec``: the process namespec.

        *@param* ``str extra_args``: extra arguments to be passed to the command line of the program.

        *@param* ``bool wait``: wait for the process to be fully started.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_NAME`` if namespec is unknown to the local Supervisor,
            * with code ``Faults.ALREADY_STARTED`` if process is ``RUNNING``,
            * with code ``Faults.ABNORMAL_TERMINATION`` if process could not be started.

        *@return* ``bool``: always ``True`` unless error.
        """
        # WARN: do NOT check OPERATION (it is used internally in DEPLOYMENT state)
        _, process = self._get_application_process(namespec)
        # update command line in process config with extra_args
        try:
            self.supvisors.info_source.update_extra_args(process.namespec, extra_args)
        except KeyError:
            # process is unknown to the local Supervisor
            # this is unexpected as Supvisors checks the configuration before it sends this request
            self.logger.error('RPCInterface.start_args: could not find {} in Supervisor processes'.format(namespec))
            raise RPCError(Faults.BAD_NAME, 'namespec {} unknown to this Supervisor instance'.format(namespec))
        # start process with Supervisor internal RPC
        try:
            rpc_interface = self.supvisors.info_source.supervisor_rpc_interface
            cb = rpc_interface.startProcess(namespec, wait)
        except RPCError as why:
            self.logger.error('start_process {} failed: {}'.format(namespec, why))
            if why.code in [Faults.NO_FILE, Faults.NOT_EXECUTABLE]:
                self.logger.warn('RPCInterface.start_args: force Supervisor internal state of {} to FATAL'
                                 .format(namespec))
                # at this stage, process is known to the local Supervisor. no need to test again
                self.supvisors.info_source.force_process_fatal(namespec, why.text)
            # else process is already started
            # this is unexpected as Supvisors checks the process state before it sends this request
            # anyway raise exception again
            raise
        return cb

    def start_process(self, strategy: EnumParameterType, namespec, extra_args='', wait=True):
        """ Start a process named namespec iaw the strategy and some of the rules file.
        WARN: the 'wait_exit' rule is not considered here.

        *@param* ``StartingStrategies strategy``: the strategy used to choose nodes, as a string or as a value.

        *@param* ``str namespec``: the process namespec (``name``,``group:name``, or ``group:*``).

        *@param* ``str extra_args``: extra arguments to be passed to command line.

        *@param* ``bool wait``: wait for the process to be fully started.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION``,
            * with code ``Faults.BAD_STRATEGY`` if strategy is unknown to **Supvisors**,
            * with code ``Faults.BAD_NAME`` if namespec is unknown to **Supvisors**,
            * with code ``Faults.ALREADY_STARTED`` if process is in a running state,
            * with code ``Faults.ABNORMAL_TERMINATION`` if process could not be started.

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check names
        application, process = self._get_application_process(namespec)
        processes = [process] if process else application.processes.values()
        # check processes are not already running
        for process in processes:
            if process.running():
                raise RPCError(Faults.ALREADY_STARTED, process.namespec)
        # start all processes
        done = True
        for process in processes:
            done &= self.supvisors.starter.start_process(strategy_enum, process, extra_args)
        self.logger.debug('RPCInterface.start_process: {} done={}'.format(process.namespec, done))
        if done:
            # one of the jobs has not been queued. something wrong happened (lack of resources ?)
            raise RPCError(Faults.ABNORMAL_TERMINATION, namespec)
        # wait until application fully RUNNING or failed
        if wait:
            def onwait():
                # check starter
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                for proc in processes:
                    if proc.stopped():
                        raise RPCError(Faults.ABNORMAL_TERMINATION, proc.namespec)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return True

    def stop_process(self, namespec, wait=True):
        """ Stop the process named namespec where it is running.

        *@param* ``str namespec``: the process namespec (``name``, ``group:name``, or ``group:*``).

        *@param* ``bool wait``: wait for process to be fully stopped.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION``
              or ``CONCILIATION``,
            * with code ``Faults.BAD_NAME`` if namespec is unknown to **Supvisors**.
            * with code ``Faults.NOT_RUNNING`` if process is in a stopped state,

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_operating_conciliation()
        # check names
        application, process = self._get_application_process(namespec)
        processes = [process] if process else application.processes.values()
        # check processes are not already running
        for process in processes:
            if process.stopped():
                raise RPCError(Faults.NOT_RUNNING, process.namespec)
        # stop all processes
        done = True
        for process in processes:
            self.logger.info('RPCInterface.stop_process: stopping process {}'.format(process.namespec))
            done &= self.supvisors.stopper.stop_process(process)
        # wait until processes are in STOPPED_STATES
        if wait and not done:
            def onwait():
                # check stopper
                if self.supvisors.stopper.in_progress():
                    return NOT_DONE_YET
                for proc in processes:
                    if proc.running():
                        raise RPCError(Faults.ABNORMAL_TERMINATION, proc.namespec)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return True

    def restart_process(self, strategy: EnumParameterType, namespec, extra_args='', wait=True):
        """ Restart a process named namespec iaw the strategy and some of the rules defined in the rules file.
        WARN: the 'wait_exit' rule is not considered here.

        *@param* ``StartingStrategies strategy``: the strategy used to choose nodes, as a string or as a value.

        *@param* ``str namespec``: the process namespec (``name``, ``group:name``, or ``group:*``).

        *@param* ``str extra_args``: extra arguments to be passed to command line. If None, use the arguments passed
        with the last call.

        *@param* ``bool wait``: wait for process to be fully stopped.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION``,
            * with code ``Faults.BAD_STRATEGY`` if strategy is unknown to **Supvisors**,
            * with code ``Faults.BAD_NAME`` if namespec is unknown to **Supvisors**,
            * with code ``Faults.ABNORMAL_TERMINATION`` if process could not be started.

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_operating()

        def onwait():
            # first wait for process to be stopped
            if onwait.waitstop:
                # job may be a boolean value if stop_process has nothing to do
                value = type(onwait.job) is bool or onwait.job()
                if value is True:
                    # done. request start application
                    onwait.waitstop = False
                    value = self.start_process(strategy, namespec, extra_args, wait)
                    if type(value) is bool:
                        return value
                    # deferred job to wait for application to be started
                    onwait.job = value
                return NOT_DONE_YET
            return onwait.job()

        onwait.delay = 0.5
        onwait.waitstop = True
        # request stop process. job is for deferred result
        onwait.job = self.stop_process(namespec, True)
        return onwait  # deferred

    def conciliate(self, strategy: EnumParameterType) -> bool:
        """ Apply the conciliation strategy only if **Supvisors** is in ``CONCILIATION`` state,
        with an ``USER`` conciliation strategy (using other strategies would trigger an automatic behavior that wouldn't
        give a chance to this XML-RPC).

        *@param* ``ConciliationStrategies strategy``: the strategy used to conciliate, as a string or as a value.

        *@throws* ``RPCError``:

            * with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``CONCILIATION``,
            * with code ``Faults.BAD_STRATEGY`` if strategy is unknown to **Supvisors**.

        *@return* ``bool``: ``True`` if conciliation is triggered, ``False`` when the conciliation strategy is ``USER``.
        """
        self._check_conciliation()
        strategy_enum = self._get_conciliation_strategy(strategy)
        # trigger conciliation
        if strategy != ConciliationStrategies.USER:
            conciliate_conflicts(self.supvisors, strategy_enum, self.supvisors.context.conflicts())
            return True
        return False

    def restart(self) -> bool:
        """ Stops all applications and restart **Supvisors** through all Supervisor daemons.

        *@throws* ``RPCError``: with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
        ``INITIALIZATION`` state.

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_from_deployment()
        self.supvisors.fsm.on_restart()
        return True

    def shutdown(self) -> bool:
        """ Stops all applications and shut down **Supvisors** through all Supervisor daemons.

        *@throws* ``RPCError``: with code ``Faults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
        ``INITIALIZATION`` state.

        *@return* ``bool``: always ``True`` unless error.
        """
        self._check_from_deployment()
        self.supvisors.fsm.on_shutdown()
        return True

    def change_log_level(self, level_param: EnumParameterType) -> bool:
        """ Change the logger level for the local **Supvisors**.
        If **Supvisors** logger is configured as ``AUTO``, this will impact the Supervisor logger too.

        *@param* ``LevelsByName level``: the new logger level, as a string or as a value.

        *@throws* ``RPCError``: with code ``Faults.BAD_LEVEL`` if level is unknown to **Supervisor**.

        *@return* ``bool``: always ``True`` unless error.
        """
        level = self._get_logger_level(level_param)
        self.logger.level = level
        for handler in self.logger.handlers:
            handler.level = level
        return True

    # utilities
    @staticmethod
    def _get_starting_strategy(strategy: EnumParameterType) -> StartingStrategies:
        """ Check if the strategy given can fit to a StartingStrategies enum. """
        return RPCInterface._get_strategy(strategy, StartingStrategies)

    @staticmethod
    def _get_conciliation_strategy(strategy: EnumParameterType) -> ConciliationStrategies:
        """ Check if the strategy given can fit to a ConciliationStrategies enum. """
        return RPCInterface._get_strategy(strategy, ConciliationStrategies)

    @staticmethod
    def _get_strategy(strategy: EnumParameterType, enum_klass: EnumClassType) -> EnumType:
        """ Check if the strategy given can fit to string or value of the StartingStrategies enum. """
        # check by string
        try:
            return enum_klass[strategy]
        except KeyError:
            # check by value
            try:
                return enum_klass(strategy)
            except ValueError:
                raise RPCError(Faults.BAD_STRATEGY, '{}'.format(strategy))

    @staticmethod
    def _get_logger_levels() -> Dict[LevelsByName, str]:
        return {level: desc for desc, level in LevelsByDescription.__dict__.items() if not desc.startswith('_')}

    @staticmethod
    def _get_logger_level(level_param: EnumParameterType) -> EnumType:
        """ Check if the strategy given can fit to string or value of the StartingStrategies enum. """
        # check by string
        if type(level_param) is str:
            level = getLevelNumByDescription(level_param)
            if level is not None:
                return level
        # check by value
        if RPCInterface._get_logger_levels().get(level_param) is None:
            raise RPCError(Faults.BAD_LEVEL, '{}'.format(level_param))
        return level_param

    def _check_from_deployment(self):
        """ Raises a BAD_SUPVISORS_STATE exception if Supvisors' state is in INITIALIZATION. """
        self._check_state([SupvisorsStates.DEPLOYMENT,
                           SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION,
                           SupvisorsStates.RESTARTING, SupvisorsStates.SHUTTING_DOWN])

    def _check_operating_conciliation(self):
        """ Raises a BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in OPERATION or CONCILIATION. """
        self._check_state([SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION])

    def _check_operating(self):
        """ Raises a BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in OPERATION. """
        self._check_state([SupvisorsStates.OPERATION])

    def _check_conciliation(self):
        """ Raises a BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in OPERATION. """
        self._check_state([SupvisorsStates.CONCILIATION])

    def _check_state(self, states):
        """ Raises a BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in one of the states. """
        if self.supvisors.fsm.state not in states:
            raise RPCError(Faults.BAD_SUPVISORS_STATE,
                           'Supvisors (state={}) not in state {} to perform request'
                           .format(self.supvisors.fsm.state.name, [state.name for state in states]))

    def _get_application_process(self, namespec):
        """ Return the ApplicationStatus and ProcessStatus corresponding to the namespec.
        A BAD_NAME exception is raised if the application or the process is not found. """
        application_name, process_name = split_namespec(namespec)
        application = self._get_application(application_name)
        process = self._get_process(application, process_name) if process_name else None
        return application, process

    def _get_application(self, application_name):
        """ Return the ApplicationStatus corresponding to the application name.
        A BAD_NAME exception is raised if the application is not found. """
        try:
            return self.supvisors.context.applications[application_name]
        except KeyError:
            raise RPCError(Faults.BAD_NAME, 'application {} unknown to Supvisors'.format(application_name))

    @staticmethod
    def _get_process(application: ApplicationStatus, process_name: str):
        """ Return the ProcessStatus corresponding to process_name in application.
        A BAD_NAME exception is raised if the process is not found. """
        try:
            return application.processes[process_name]
        except KeyError:
            raise RPCError(Faults.BAD_NAME, 'process={} unknown in application={}'
                           .format(process_name, application.application_name))

    @staticmethod
    def _get_internal_process_rules(process):
        """ Return a dictionary with the rules of the process. """
        result = process.rules.serial()
        result.update({'application_name': process.application_name, 'process_name': process.process_name})
        return result

    def _get_local_info(self, info):
        """ Create a payload from Supervisor process info. """
        sub_info = extract_process_info(info)
        namespec = make_namespec(info['group'], info['name'])
        try:
            sub_info['extra_args'] = self.supvisors.info_source.get_extra_args(namespec)
        except KeyError:
            self.logger.trace('RPCInterface._get_local_info: cannot get extra_args from unknown program={}'
                              .format(namespec))
        return sub_info
