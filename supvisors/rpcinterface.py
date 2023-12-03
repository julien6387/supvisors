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
from typing import Callable, Type, Union

from supervisor.http import NOT_DONE_YET
from supervisor.loggers import Logger, LevelsByName, LevelsByDescription, getLevelNumByDescription, LOG_LEVELS_BY_NUM
from supervisor.options import make_namespec, split_namespec, VERSION
from supervisor.xmlrpc import Faults, RPCError

from .application import ApplicationStatus
from .strategy import get_supvisors_instance, conciliate_conflicts
from .ttypes import *
from .utils import extract_process_info

# get Supvisors version from file
here = os.path.abspath(os.path.dirname(__file__))
version_txt = os.path.join(here, 'version.txt')
with open(version_txt, 'r') as ver:
    API_VERSION = ver.read().split('=')[1].strip()


def startProcess(self, name: str, wait: bool = True):
    """ Overridden startProcess to handle a disabled process.

    :param str name: the process namespec
    :param bool wait: wait for the process to be fully started
    :return: always ``True`` unless error.
    :rtype: bool
    """
    # raise exception is process is disabled
    self._update('startProcess')
    group, process = self._getGroupAndProcess(name)
    if process and process.config.disabled:
        raise RPCError(SupvisorsFaults.DISABLED.value, name)
    # call normal behavior
    # original method has been renamed on-the-fly as _startProcess
    return self._startProcess(name, wait)


class RPCInterface(object):
    """ This class holds the XML-RPC extension provided by **Supvisors**. """

    # annotation types for RPC
    EnumParameterType = Union[str, int]
    OnWaitReturnType = Union[Type[NOT_DONE_YET], bool]
    WaitReturnType = Union[Callable[[], OnWaitReturnType], bool]
    OnWaitStringReturnType = Union[Type[NOT_DONE_YET], str]
    WaitStringReturnType = Union[Callable[[], OnWaitStringReturnType], str]

    def __init__(self, supvisors: Any):
        """ Initialization of the attributes.

        :param Supvisors supvisors: the global Supvisors structure
        """
        self.supvisors = supvisors
        self.logger: Logger = supvisors.logger
        self.logger.info(f'RPCInterface: using Supvisors={API_VERSION} Supervisor={VERSION}')

    # RPC Status methods
    def get_api_version(self) -> str:
        """ Return the version of the RPC API used by **Supvisors**.

        :return: the **Supvisors** version.
        :rtype: str
        """
        self.logger.blather('RPCInterface.get_api_version: do NOT make it static as it breaks the RPC Interface')
        return API_VERSION

    def get_supvisors_state(self) -> Payload:
        """ Return the state and modes of **Supvisors**.
        The **Supvisors** state is the FSM state and is a reflection of the **Supvisors** *Master* instance state.
        The **Supvisors** modes provides the identifiers of the **Supvisors** instances having starting
        or stopping jobs in progress.

        :return: the state and modes of **Supvisors**.
        :rtype: dict[str, Any]
        """
        return self.supvisors.context.get_state_modes()

    def get_master_identifier(self) -> str:
        """ Get the identification of the **Supvisors** instance elected as **Supvisors** *Master*.

        :return: the identifier of the **Supvisors** *Master* instance.
        :rtype: str
        """
        return self.supvisors.context.master_identifier

    def get_strategies(self) -> Payload:
        """ Get the default strategies applied by **Supvisors**:

            * auto-fencing: Supvisors instance isolation if it becomes inactive,
            * starting: used in the ``DEPLOYMENT`` state to start applications,
            * conciliation: used in the ``CONCILIATION`` state to conciliate conflicts.

        :return: a structure containing information about the strategies applied.
        :rtype: dict[str, Any]
        """
        options = self.supvisors.options
        return {'auto-fencing': options.auto_fence,
                'starting': options.starting_strategy.name,
                'conciliation': options.conciliation_strategy.name}

    def get_all_instances_info(self) -> PayloadList:
        """ Get information about all **Supvisors** instances.

        :return: a list of structures containing information about all **Supvisors** instances.
        :rtype: list[dict[str, Any]]
        """
        return [self.get_instance_info(identifier)
                for identifier in sorted(self.supvisors.context.instances)]

    def get_instance_info(self, identifier: str) -> Payload:
        """ Get information about the **Supvisors** instance identified by ``identifier``.

        :param str identifier: the identifier of the Supvisors instance where the Supervisor daemon is running.
        :return: a structure containing information about the **Supvisors** instance.
        :rtype: dict[str, Any]
        :raises RPCError: with code ``Faults.INCORRECT_PARAMETERS`` if ``identifier`` is unknown to **Supvisors**.
        """
        try:
            status = self.supvisors.context.instances[identifier]
        except KeyError:
            message = f'{identifier} unknown to Supvisors'
            self.logger.error(f'RPCInterface.get_instance_info: {message}')
            raise RPCError(Faults.INCORRECT_PARAMETERS, message)
        # get Supvisors instance status and complement with Starter and Stopper progress
        return status.serial()

    def get_all_applications_info(self) -> PayloadList:
        """ Get information about all applications managed in **Supvisors**.

        :return: a list of structures containing information about all applications.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
            ``INITIALIZATION`` state.
        """
        self._check_from_deployment()
        return [self.get_application_info(application_name)
                for application_name in self.supvisors.context.applications.keys()]

    def get_application_info(self, application_name: str) -> Payload:
        """ Get information about an application named ``application_name``.

        :param str application_name: the name of the application.
        :return: a structure containing information about the application.
        :rtype: dict[str, Any]
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state ;
            ``Faults.BAD_NAME`` if ``application_name`` is unknown to **Supvisors**.
        """
        self._check_from_deployment()
        return self._get_application(application_name).serial()

    def get_application_rules(self, application_name: str) -> Payload:
        """ Get the rules used to start / stop the application named ``application_name``.

        :param str application_name: the name of the application.
        :return: a structure containing the rules.
        :rtype: dict[str, Any]
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state ;
            ``Faults.BAD_NAME`` if ``application_name`` is unknown to **Supvisors**.
        """
        self._check_from_deployment()
        result = self._get_application(application_name).rules.serial()
        result.update({'application_name': application_name})
        return result

    def get_all_process_info(self) -> PayloadList:
        """ Get synthetic information about all processes.

        :return: a list of structures containing information about the processes.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
            ``INITIALIZATION`` state.
        """
        self._check_from_deployment()
        return [process.serial()
                for application in self.supvisors.context.applications.values()
                for process in application.processes.values()]

    def get_process_info(self, namespec: str) -> PayloadList:
        """ Get synthetic information about a process named ``namespec``.
        It gives a synthetic status, based on the process information coming from all running **Supvisors** instances.

        :param str namespec: the process namespec (``name``, ``group:name``, or ``group:*``).
        :return: a list of structures containing information about the processes.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors**.
        """
        self._check_from_deployment()
        application, process = self._get_application_process(namespec)
        if process:
            return [process.serial()]
        return [proc.serial() for proc in application.processes.values()]

    def get_all_local_process_info(self) -> PayloadList:
        """ Get information about all processes located on this Supvisors instance.
        It is a subset of ``supervisor.getProcessInfo``, used by **Supvisors** in ``INITIALIZATION`` state,
        and giving the extra arguments of the process.

        :return: a list of structures containing information about the processes.
        :rtype: list[dict[str, Any]]
        """
        supervisor_intf = self.supvisors.supervisor_data.supervisor_rpc_interface
        all_info = supervisor_intf.getAllProcessInfo()
        return [self._get_local_info(info) for info in all_info]

    def get_local_process_info(self, namespec: str) -> Payload:
        """ Get local information about a process named ``namespec``.
        It is a subset of ``supervisor.getProcessInfo``, used by **Supvisors** in ``INITIALIZATION`` state,
        and giving the extra arguments of the process.

        :param str namespec: the process namespec (``name``, ``group:name``).
        :return: a structure containing information about the process.
        :rtype: dict[str, Any]
        :raises RPCError: with code ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors**.
        """
        supervisor_intf = self.supvisors.supervisor_data.supervisor_rpc_interface
        info = supervisor_intf.getProcessInfo(namespec)
        return self._get_local_info(info)

    def get_process_rules(self, namespec: str) -> PayloadList:
        """ Get the rules used to start / stop the process named ``namespec``.

        :param str namespec: the process namespec (``name``, ``group:name``, or ``group:*``).
        :return: a list of structures containing the rules.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors**.
        """
        self._check_from_deployment()
        application, process = self._get_application_process(namespec)
        if process:
            return [self._get_internal_process_rules(process)]
        return [self._get_internal_process_rules(proc) for proc in application.processes.values()]

    def get_conflicts(self) -> PayloadList:
        """ Get the conflicting processes among the managed applications.

        :return: a list of structures containing information about the conflicting processes.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
            ``INITIALIZATION`` state,
        """
        self._check_from_deployment()
        return [process.serial() for process in self.supvisors.context.conflicts()]

    # RPC Command methods
    def start_application(self, strategy: EnumParameterType, application_name: str,
                          wait: bool = True) -> WaitReturnType:
        """ Start the *Managed* application named ``application_name`` iaw the strategy and the rules file.
        To start *Unmanaged* applications, use ``supervisor.start('group:*')``.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str application_name: the name of the application.
        :param bool wait: if ``True``, wait for the application to be fully started before returning.
        :return: always ``True`` unless error or nothing to start.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if ``application_name`` is unknown to **Supvisors** ;
            ``SupvisorsFaults.NOT_MANAGED`` if the application is not *Managed* in **Supvisors** ;
            ``Faults.ALREADY_STARTED`` if the application is ``STARTING``, ``STOPPING`` or ``RUNNING`` ;
            ``Faults.ABNORMAL_TERMINATION`` if the application could not be started.
        """
        self.logger.trace(f'RPCInterface.start_application: strategy={strategy} application={application_name}'
                          f' wait={wait}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check application is known
        if application_name not in self.supvisors.context.applications.keys():
            raise RPCError(Faults.BAD_NAME, application_name)
        # check application is managed
        if application_name not in self.supvisors.context.get_managed_applications():
            raise RPCError(SupvisorsFaults.NOT_MANAGED.value, application_name)
        # check application is not already RUNNING
        application = self.supvisors.context.applications[application_name]
        if application.state != ApplicationStates.STOPPED:
            raise RPCError(Faults.ALREADY_STARTED, application_name)
        # TODO: develop a predictive model to check if starting can be achieved
        # if impossible due to a lack of resources, second try without optional
        # return false if still impossible
        self.supvisors.starter.start_application(strategy_enum, application)
        in_progress = self.supvisors.starter.in_progress()
        self.logger.debug(f'RPCInterface.start_application: {application_name} in_progress={in_progress}')
        # wait until application fully RUNNING or (failed)
        if wait and in_progress:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check starter
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                if application.state != ApplicationStates.RUNNING:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, application_name)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return in_progress

    def stop_application(self, application_name: str, wait: bool = True) -> WaitReturnType:
        """ Stop the *Managed* application named ``application_name``.
        To stop *Unmanaged* applications, use ``supervisor.stop('group:*')``.

        :param str application_name: the name of the application.
        :param bool wait: if ``True``, wait for the application to be fully stopped.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` or ``CONCILIATION`` ;
            ``Faults.BAD_NAME`` if ``application_name`` is unknown to **Supvisors** ;
            ``SupvisorsFaults.NOT_MANAGED`` if the application is not *Managed* in **Supvisors** ;
            ``Faults.NOT_RUNNING`` if application is ``STOPPED``.
        """
        self.logger.trace(f'RPCInterface.stop_application: application={application_name} wait={wait}')
        self._check_operating_conciliation()
        # check application is known
        if application_name not in self.supvisors.context.applications.keys():
            raise RPCError(Faults.BAD_NAME, application_name)
        # check application is managed
        if application_name not in self.supvisors.context.get_managed_applications():
            raise RPCError(SupvisorsFaults.NOT_MANAGED.value, application_name)
        # check application is not already STOPPED
        application = self.supvisors.context.applications[application_name]
        if not application.has_running_processes():
            raise RPCError(Faults.NOT_RUNNING, application_name)
        # stop the application
        self.supvisors.stopper.stop_application(application)
        in_progress = self.supvisors.stopper.in_progress()
        self.logger.debug(f'RPCInterface.stop_application: {application_name} in_progress={in_progress}')
        # wait until application fully STOPPED
        if wait and in_progress:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check stopper
                if self.supvisors.stopper.in_progress():
                    return NOT_DONE_YET
                if application.state != ApplicationStates.STOPPED:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, application_name)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return in_progress

    def restart_application(self, strategy: EnumParameterType, application_name: str,
                            wait: bool = True) -> WaitReturnType:
        """ Restart the application named ``application_name`` iaw the strategy and the rules file.
        To restart *Unmanaged* applications, use ``supervisor.stop('group:*')``, then ``supervisor.start('group:*')``.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str application_name: the name of the application.
        :param bool wait: if ``True``, wait for the application to be fully restarted.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if ``application_name`` is unknown to **Supvisors** ;
            ``SupvisorsFaults.NOT_MANAGED`` if the application is not *Managed* in **Supvisors** ;
            ``Faults.ABNORMAL_TERMINATION`` if application could not be restarted.
        """
        self.logger.trace(f'RPCInterface.restart_application: strategy={strategy} application={application_name}'
                          f' wait={wait}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check application name
        application = self._get_application(application_name)
        # restart the application
        self.supvisors.stopper.restart_application(strategy_enum, application)
        in_progress = self.supvisors.stopper.in_progress() or self.supvisors.starter.in_progress()
        if not in_progress:
            self.logger.error(f'RPCInterface.restart_application: failed restarting {application_name}')
            raise RPCError(Faults.ABNORMAL_TERMINATION, f'failed restarting {application_name}')
        # theoretically, wait until application is stopped then running
        # in practice, just check stopper and start activity, even if not fully related to this call
        if wait:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # stopping phase
                if onwait.waitstop:
                    if not self.supvisors.stopper.in_progress():
                        self.logger.debug(f'RPCInterface.restart_application: stopping {application_name} completed')
                        onwait.waitstop = False
                    return NOT_DONE_YET
                # starting phase
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                self.logger.debug(f'RPCInterface.restart_application: starting {application_name} completed')
                if application.stopped():
                    self.logger.error(f'RPCInterface.restart_application: {application_name} still stopped')
                    raise RPCError(Faults.ABNORMAL_TERMINATION, f'failed to restart {application_name}')
                return True

            onwait.delay = 0.5
            onwait.waitstop = True
            return onwait  # deferred
        return True

    def start_args(self, namespec: str, extra_args: str, wait: bool = True) -> WaitReturnType:
        """ Start the process named ``namespec`` on the local Supvisors instance.
        The behaviour is different from ``supervisor.startProcess`` as it sets the process state to ``FATAL``
        instead of throwing an exception to the RPC client.
        This RPC makes it also possible to pass extra arguments to the program command line.

        :param str namespec: the process namespec.
        :param str extra_args: the extra arguments to be passed to the command line of the program.
        :param bool wait: if ``True``, wait for the process to be fully started.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to the local Supervisor ;
            ``SupvisorsFaults.DISABLED`` if process is *disabled* ;
            ``Faults.ALREADY_STARTED`` if process is ``RUNNING`` ;
            ``Faults.ABNORMAL_TERMINATION`` if process could not be started.
        """
        # WARN: do NOT check OPERATION (it is used internally in DEPLOYMENT state)
        _, process = self._get_application_process(namespec)
        # update command line in process config with extra_args
        try:
            self.supvisors.supervisor_data.update_extra_args(process.namespec, extra_args)
        except KeyError:
            # process is unknown to the local Supervisor
            # this is unexpected as Supvisors checks the configuration before it sends this request
            self.logger.error(f'RPCInterface.start_args: could not find {namespec} in Supervisor processes')
            raise RPCError(Faults.BAD_NAME, f'namespec {namespec} unknown to this Supervisor instance')
        # start process with Supervisor internal RPC
        try:
            rpc_interface = self.supvisors.supervisor_data.supervisor_rpc_interface
            cb = rpc_interface.startProcess(namespec, wait)
        except RPCError as why:
            self.logger.error(f'RPCInterface.start_args: start_process {namespec} failed - {why}')
            if why.code in [Faults.NO_FILE, Faults.NOT_EXECUTABLE]:
                self.logger.warn(f'RPCInterface.start_args: force Supervisor internal state of {namespec} to FATAL')
                # at this stage, process is known to the local Supervisor. no need to test again
                self.supvisors.supervisor_data.force_process_fatal(namespec, why.text)
            # else process is already started or disabled
            # raise exception again
            raise
        return cb

    def start_process(self, strategy: EnumParameterType, namespec: str, extra_args: str = '',
                      wait: bool = True) -> WaitReturnType:
        """ Start a process named ``namespec`` iaw the strategy and the rules file.
        WARN: the 'wait_exit' rule is not considered here.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str namespec: the process namespec (``name``,``group:name``, or ``group:*``).
        :param str extra_args: the optional extra arguments to be passed to command line.
        :param bool wait: if ``True``, wait for the process to be fully started.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors** ;
            ``Faults.ALREADY_STARTED`` if process is in a running state ;
            ``Faults.ABNORMAL_TERMINATION`` if process could not be started.
        """
        self.logger.trace(f'RPCInterface.start_process: namespec={namespec} strategy={strategy} extra_args={extra_args}'
                          f' wait={wait}')
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
        for process in processes:
            self.supvisors.starter.start_process(strategy_enum, process, extra_args)
        in_progress = self.supvisors.starter.in_progress()
        self.logger.debug(f'RPCInterface.start_process: {process.namespec} in_progress={in_progress}')
        if not in_progress:
            # one of the jobs has not been queued. something wrong happened (lack of resources ?)
            self.logger.error(f'RPCInterface.start_process: failed starting {process.namespec}')
            raise RPCError(Faults.ABNORMAL_TERMINATION, namespec)
        # wait until application fully RUNNING or failed
        if wait:
            def onwait() -> RPCInterface.OnWaitReturnType:
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

    def start_any_process(self, strategy: EnumParameterType, regex: str, extra_args: str = '',
                          wait: bool = True) -> WaitStringReturnType:
        """ Start one process among those matching the ``regex`` iaw the strategy and the rules file.
        WARN: the 'wait_exit' rule is not considered here.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str regex: a regular expression to match process namespecs.
        :param str extra_args: the optional extra arguments to be passed to command line.
        :param bool wait: if ``True``, wait for the process to be fully started.
        :return: the namespec of the process started unless error.
        :rtype: str
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if no running process found matching ``regex`` in **Supvisors** ;
            ``Faults.ABNORMAL_TERMINATION`` if process could not be started.
        """
        self.logger.trace(f'RPCInterface.start_process: regex={regex} strategy={strategy} extra_args={extra_args}'
                          f' wait={wait}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # get the processes whose namespec matches the regex and that are not running
        processes = self.supvisors.context.find_runnable_processes(regex)
        namespec = next((process.namespec for process in processes
                         if get_supvisors_instance(self.supvisors, strategy_enum, process.possible_identifiers(),
                                                   process.rules.expected_load)), None)
        if not namespec:
            raise RPCError(Faults.BAD_NAME, f'no candidate process matching "{regex}"')
        # start the chosen one and return its namespec
        bool_or_callable = self.start_process(strategy, namespec, extra_args, wait)
        if wait and callable(bool_or_callable):
            def onwait() -> RPCInterface.OnWaitStringReturnType:
                if bool_or_callable() is True:
                    return namespec
                return NOT_DONE_YET
            onwait.delay = 0.5
            return onwait  # deferred
        return namespec

    def stop_process(self, namespec: str, wait: bool = True) -> WaitReturnType:
        """ Stop the process named ``namespec`` on the **Supvisors** instance where it is running.

        :param str namespec: the process namespec (``name``, ``group:name``, or ``group:*``).
        :param bool wait: if ``True``, wait for process to be fully stopped.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` or ``CONCILIATION`` ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors** ;
            ``Faults.NOT_RUNNING`` if process is in a stopped state.
        """
        self._check_operating_conciliation()
        # check names
        application, process = self._get_application_process(namespec)
        processes = [process] if process else application.processes.values()
        # stop all processes
        for process in processes:
            self.logger.debug(f'RPCInterface.stop_process: stopping process={process.namespec}')
            self.supvisors.stopper.stop_process(process, trigger=False)
        self.supvisors.stopper.next()
        in_progress = self.supvisors.stopper.in_progress()
        # if already done, that would mean nothing was running
        if not in_progress:
            self.logger.error(f'RPCInterface.stop_process: failed stopping {namespec}')
            raise RPCError(Faults.NOT_RUNNING, namespec)
        # theoretically, wait until processes are stopped
        # in practice, just check stopper, even if not fully related to this call
        if wait:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check stopper
                if self.supvisors.stopper.in_progress():
                    return NOT_DONE_YET
                self.logger.debug(f'RPCInterface.stop_process: stopping {namespec} completed')
                proc_errors = []
                for proc in processes:
                    if proc.running():
                        self.logger.error(f'RPCInterface.stop_process: process={proc.namespec} still running')
                        proc_errors.append(proc.namespec)
                if proc_errors:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, ' '.join(proc_errors))
                return True
            onwait.delay = 0.5
            return onwait  # deferred
        return True

    def restart_process(self, strategy: EnumParameterType, namespec: str, extra_args: str = '',
                        wait: bool = True) -> WaitReturnType:
        """ Restart the process named ``namespec`` iaw the strategy and the rules defined in the rules file.
        Note that the process will not necessarily start in the same **Supvisors** instance as the starting context
        will be re-evaluated.
        WARN: the 'wait_exit' rule is not considered here.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str namespec: the process namespec (``name``, ``group:name``, or ``group:*``).
        :param str extra_args: the extra arguments to be passed to the command line.
        :param bool wait: if ``True``, wait for process to be fully restarted.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors** ;
            ``Faults.ABNORMAL_TERMINATION`` if process could not be restarted.
        """
        self.logger.trace(f'RPCInterface.restart_process: strategy={strategy} process={namespec} args={extra_args}'
                          ' wait={wait}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check namespec
        application, process = self._get_application_process(namespec)
        processes = [process] if process else application.processes.values()
        # restart all processes
        for process in processes:
            self.logger.debug(f'RPCInterface.restart_process: restarting process={process.namespec}')
            self.supvisors.stopper.restart_process(strategy_enum, process, extra_args)
        in_progress = self.supvisors.stopper.in_progress() or self.supvisors.starter.in_progress()
        if not in_progress:
            self.logger.error(f'RPCInterface.restart_process: failed restarting {namespec}')
            raise RPCError(Faults.ABNORMAL_TERMINATION, f'failed restarting {namespec}')
        # theoretically, wait until processes are stopped then running
        # in practice, just check stopper and start activity, even if not fully related to this call
        if wait:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # stopping phase
                if onwait.waitstop:
                    if not self.supvisors.stopper.in_progress():
                        self.logger.debug(f'RPCInterface.restart_process: stopping {namespec} completed')
                        onwait.waitstop = False
                    return NOT_DONE_YET
                # starting phase
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                self.logger.debug(f'RPCInterface.restart_process: starting {namespec} completed')
                proc_errors = []
                for proc in processes:
                    if proc.stopped():
                        self.logger.error(f'RPCInterface.restart_process: process={proc.namespec} still stopped')
                        proc_errors.append(proc.namespec)
                if proc_errors:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, ' '.join(proc_errors))
                return True
            onwait.delay = 0.5
            onwait.waitstop = True
            return onwait  # deferred
        return True

    def _increase_numprocs(self, process_namespecs: NameList, wait: bool) -> WaitReturnType:
        """ Following a call to update_numprocs, a number of processes have to be added to the internal configuration.

        :param list[str] process_namespecs: the namespecs of the processes to stop and remove
        :param bool wait: if ``True``, wait for the confirmation that processes have been added to Supvisors.
        :return: a callable if wait is requested or ``True``.
        :rtype: bool
        """
        # no special job to do if wait not wanted. all the necessary configuration is already in progress
        if wait:
            # if the value is lower than the current one, processes must be stopped before they are deleted
            self.logger.debug(f'RPCInterface._increase_numprocs: new processes={process_namespecs}')
            local_identifier = self.supvisors.mapper.local_identifier

            # mandatory wait until processes are added to Supvisors
            def onwait() -> RPCInterface.OnWaitReturnType:
                for namespec in process_namespecs:
                    # process may have been deleted if there is no more Supervisor instance supporting it
                    try:
                        proc = self.supvisors.context.get_process(namespec)
                        if local_identifier not in proc.info_map:
                            return NOT_DONE_YET
                    except KeyError:
                        self.logger.debug(f'RPCInterface._decrease_numprocs: processes {namespec} does not exist yet')
                        return NOT_DONE_YET
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return True

    def _decrease_numprocs(self, process_namespecs: NameList, wait: bool) -> WaitReturnType:
        """ Following a call to update_numprocs, a number of processes have to be stopped and removed.

        :param list[str] process_namespecs: the namespecs of the processes to stop and remove
        :param bool wait: if ``True``, wait for the confirmation that processes have been removed from Supvisors.
        :return: a callable for the deferred actions.
        :rtype: Callable[[], bool]
        """
        # if the value is lower than the current one, processes must be stopped before they are deleted
        self.logger.debug(f'RPCInterface._decrease_numprocs: obsolete processes={process_namespecs}')
        local_identifier = self.supvisors.mapper.local_identifier
        processes_to_stop = list(filter(lambda x: x.running_on(local_identifier),
                                        [self.supvisors.context.get_process(del_namespec)
                                         for del_namespec in process_namespecs]))
        for process in processes_to_stop:
            self.logger.debug(f'RPCInterface._decrease_numprocs: stopping process={process.namespec}')
            self.supvisors.stopper.stop_process(process, [local_identifier], False)
        self.supvisors.stopper.next()

        # mandatory wait until processes are removed from Supervisor because processes will be deleted
        # only when they are properly stopped
        # optional wait is about waiting for Supvisors to receive the events and consolidate its internal data
        def onwait() -> RPCInterface.OnWaitReturnType:
            # check stop phase
            if onwait.checkstop:
                # check stopper
                if self.supvisors.stopper.in_progress():
                    return NOT_DONE_YET
                onwait.checkstop = False
                # when stopper is done, delete the processes that have been stopped
                proc_errors = []
                for proc in processes_to_stop:
                    if proc.running():
                        self.logger.error(f'RPCInterface._decrease_numprocs: process={proc.namespec} still running')
                        proc_errors.append(proc.namespec)
                        # WARN: do not delete a process that is running
                        process_namespecs.remove(proc.namespec)
                # complete removal in Supervisor
                self.logger.debug(f'RPCInterface._decrease_numprocs: delete processes {process_namespecs}')
                self.supvisors.supervisor_data.delete_processes(process_namespecs)
                if proc_errors:
                    raise RPCError(Faults.ABNORMAL_TERMINATION, ' '.join(proc_errors))
            # when removal is done in Supervisor, wait for confirmation in Supvisors
            if wait and not onwait.checkstop:
                for namespec in process_namespecs:
                    # process may have been deleted if there is no more Supervisor instance supporting it
                    try:
                        proc = self.supvisors.context.get_process(namespec)
                        if local_identifier in proc.info_map:
                            return NOT_DONE_YET
                    except KeyError:
                        self.logger.debug(f'RPCInterface._decrease_numprocs: processes {namespec} has been deleted')
            return True

        onwait.delay = 0.5
        onwait.checkstop = True
        return onwait  # deferred

    def update_numprocs(self, program_name: str, numprocs: int, wait: bool = True) -> WaitReturnType:
        """ Update dynamically the numprocs of the program.
        Implementation of Supervisor issue #177 - Dynamic numproc change.

        :param str program_name: the program name, as found in the section of the Supervisor configuration files.
            Programs, FastCGI programs and event listeners are supported.
        :param int numprocs: the new numprocs value (must be strictly positive).
        :param bool wait: if ``True``, wait for the confirmation that processes have been added
            or removed into Supvisors.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.BAD_NAME`` if ``program_name`` is unknown to **Supvisors** ;
            ``Faults.INCORRECT_PARAMETERS`` if ``numprocs`` is not a strictly positive integer ;
            ``SupvisorsFaults.SUPVISORS_CONF_ERROR`` if the program configuration does not support numprocs.
        """
        self.logger.trace(f'RPCInterface.update_numprocs: program={program_name} numprocs={numprocs}')
        self._check_operating()
        # test that program_name is known to the ServerOptions
        if program_name not in self.supvisors.server_options.program_processes:
            self.logger.error(f'RPCInterface.update_numprocs: program={program_name} unknown')
            raise RPCError(Faults.BAD_NAME, f'program {program_name} unknown to Supvisors')
        # test that numprocs is strictly positive
        try:
            value = int(numprocs)
            assert value > 0
        except (ValueError, AssertionError):
            self.logger.error(f'RPCInterface.update_numprocs: program={program_name} incorrect numprocs={numprocs}')
            raise RPCError(Faults.INCORRECT_PARAMETERS,
                           f'incorrect value for numprocs: {numprocs} (integer > 0 expected)')
        try:
            add_namespecs, del_namespecs = self.supvisors.supervisor_data.update_numprocs(program_name, value)
        except ValueError as exc:
            self.logger.error(f'RPCInterface.update_numprocs: numprocs invalid to program={program_name}')
            raise RPCError(SupvisorsFaults.SUPVISORS_CONF_ERROR.value, f'numprocs not applicable: {exc}')
        # use different methods for the next activities
        if add_namespecs:
            return self._increase_numprocs(add_namespecs, wait)
        if del_namespecs:
            return self._decrease_numprocs(del_namespecs, wait)
        return True

    def enable(self, program_name: str, wait: bool = True) -> WaitReturnType:
        """ Enable the process, i.e. remove the disabled flag on the corresponding processes if set.
        This information is persisted on disk so that it is taken into account on Supervisor restart.
        Implementation of Supervisor issue #591 - New Feature: disable/enable.

        :param str program_name: the name of the program
        :param bool wait: if ``True``, wait for the corresponding processes to be fully stopped.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.BAD_NAME`` if ``program_name`` is unknown to **Supvisors**.
        """
        self.logger.trace(f'RPCInterface.enable: {program_name}')
        self._check_operating()
        # test that program_name is known to the ServerOptions
        if program_name not in self.supvisors.server_options.program_processes:
            self.logger.error(f'RPCInterface.enable: program={program_name} unknown')
            raise RPCError(Faults.BAD_NAME, f'program {program_name} unknown to Supvisors')
        # re-enable the corresponding process to be started
        self.supvisors.supervisor_data.enable_program(program_name)
        if wait:
            # get corresponding subprocesses
            subprocesses = self.supvisors.supervisor_data.get_subprocesses(program_name)
            local_identifier = self.supvisors.mapper.local_identifier

            # wait until processes are removed from Supvisors
            def onwait() -> RPCInterface.OnWaitReturnType:
                for namespec in subprocesses:
                    proc = self._get_application_process(namespec)[1]
                    if proc.disabled_on(local_identifier):
                        return NOT_DONE_YET
                return True

            # deferred
            onwait.delay = 0.5
            return onwait
        return True

    def disable(self, program_name: str, wait: bool = True) -> WaitReturnType:
        """ Disable the program, i.e. stop the corresponding processes if necessary and prevent them to start.
        This information is persisted on disk so that it is taken into account on Supervisor restart.
        Implementation of Supervisor issue #591 - New Feature: disable/enable.

        :param str program_name: the name of the program
        :param bool wait: if ``True``, wait for the corresponding processes to be fully stopped.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.BAD_NAME`` if ``program_name`` is unknown to **Supvisors**.
        """
        self.logger.trace(f'RPCInterface.disable: {program_name}')
        self._check_operating()
        # test that program_name is known to the ServerOptions
        if program_name not in self.supvisors.server_options.program_processes:
            self.logger.error(f'RPCInterface.disable: program={program_name} unknown')
            raise RPCError(Faults.BAD_NAME, f'program {program_name} unknown to Supvisors')
        # whatever they are already stopped or not, it is safe to disable the processes right now
        self.supvisors.supervisor_data.disable_program(program_name)
        # get corresponding subprocesses
        subprocesses = self.supvisors.supervisor_data.get_subprocesses(program_name)
        # stop all running processes related to the program
        self.logger.debug(f'RPCInterface.disable: {program_name} - processes={subprocesses}')
        local_identifier = self.supvisors.mapper.local_identifier
        processes_to_stop = list(filter(lambda x: x.running_on(local_identifier),
                                        [self._get_application_process(namespec)[1]
                                         for namespec in subprocesses]))
        for process in processes_to_stop:
            self.logger.debug(f'RPCInterface.disable: stopping process={process.namespec}')
            self.supvisors.stopper.stop_process(process, [local_identifier], False)
        self.supvisors.stopper.next()
        if wait:
            # wait until processes are in STOPPED_STATES
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check stopper
                if onwait.waitstop:
                    if self.supvisors.stopper.in_progress():
                        return NOT_DONE_YET
                    onwait.waitstop = False
                    # report errors if any
                    proc_errors = []
                    for proc in processes_to_stop:
                        if proc.running():
                            self.logger.error(f'RPCInterface.disable: process={proc.namespec} still running')
                            proc_errors.append(proc.namespec)
                    if proc_errors:
                        raise RPCError(Faults.ABNORMAL_TERMINATION, ' '.join(proc_errors))
                # wait until processes are disabled in Supvisors
                if not onwait.waitstop:
                    for namespec in subprocesses:
                        proc = self._get_application_process(namespec)[1]
                        if not proc.disabled_on(local_identifier):
                            return NOT_DONE_YET
                return True

            # deferred
            onwait.delay = 0.5
            onwait.waitstop = True
            return onwait
        return True

    def conciliate(self, strategy: EnumParameterType) -> bool:
        """ Apply the conciliation strategy only if **Supvisors** is in ``CONCILIATION`` state and if the default
        conciliation strategy is ``USER`` (using other strategies would trigger an automatic behavior that wouldn't
        give a chance to this XML-RPC).

        :param ConciliationStrategies strategy: the strategy used to conciliate, as a string or as a value.
        :return: ``True`` if conciliation is triggered, ``False`` when the conciliation strategy is ``USER``.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``CONCILIATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors**.
        """
        self._check_conciliation()
        strategy_enum = self._get_conciliation_strategy(strategy)
        # trigger conciliation
        if strategy_enum != ConciliationStrategies.USER:
            conciliate_conflicts(self.supvisors, strategy_enum, self.supvisors.context.conflicts())
            return True
        return False

    def restart_sequence(self, wait=True) -> WaitReturnType:
        """ Triggers the whole starting sequence by going back to the DEPLOYMENT state.

        :param bool wait: if ``True``, wait for **Supvisors** to reach the OPERATION state.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in
            ``OPERATION`` state.
        """
        self._check_operating()
        # call for restart sequence. will be re-directed to master if local Supvisors instance is not
        self.supvisors.fsm.on_restart_sequence()
        if wait:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # first wait for DEPLOYMENT state
                if onwait.wait_state == SupvisorsStates.DEPLOYMENT:
                    if self.supvisors.fsm.state == SupvisorsStates.DEPLOYMENT:
                        onwait.wait_state = SupvisorsStates.OPERATION
                    return NOT_DONE_YET
                else:
                    # when reached, wait for OPERATION state
                    if self.supvisors.fsm.state != SupvisorsStates.OPERATION:
                        return NOT_DONE_YET
                    return True

            onwait.delay = 0.5
            onwait.wait_state = SupvisorsStates.DEPLOYMENT
            return onwait  # deferred
        return True

    def restart(self) -> bool:
        """ Stops all applications and restart **Supvisors** through all Supervisor daemons.

        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ```SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still
            in state ``INITIALIZATION`` or has no Master instance to perform the request.
        """
        self._check_from_deployment()
        self.supvisors.fsm.on_restart()
        return True

    def shutdown(self) -> bool:
        """ Stops all applications and shut down **Supvisors** through all Supervisor daemons.

        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ```SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still
            in state ``INITIALIZATION`` or has no Master instance to perform the request.
        """
        self._check_from_deployment()
        self.supvisors.fsm.on_shutdown()
        return True

    def end_sync(self, master: str = '') -> bool:
        """ Ends the synchronization phase on the basis of the known situation.

        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``INITIALIZATION`` ;
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if the synchronization is ending ;
            ``Faults.INCORRECT_PARAMETERS`` if the synchro_options does not include ``USER`` ;
            ``Faults.BAD_NAME`` if master is an unknown Supvisors identifier ;
            ``Faults.NOT_RUNNING`` if the selected Master Supvisors instance is not in state ``RUNNING``.
        """
        self._check_state([SupvisorsStates.INITIALIZATION])
        if self.supvisors.context.master_identifier:
            raise RPCError(SupvisorsFaults.BAD_SUPVISORS_STATE, 'Supvisors synchronization ending')
        if SynchronizationOptions.USER not in self.supvisors.options.synchro_options:
            raise RPCError(Faults.INCORRECT_PARAMETERS, 'USER expected in synchro_options')
        if master:
            if master not in self.supvisors.context.instances:
                raise RPCError(Faults.BAD_NAME, f'unknown Supvisors identifier: {master}')
            status = self.supvisors.context.instances[master]
            if status.state != SupvisorsInstanceStates.RUNNING:
                raise RPCError(Faults.NOT_RUNNING, f'Supvisors instance={master} is not RUNNING ({status.state.name})')
        # checks passed so trigger the request
        self.supvisors.fsm.on_end_sync(master)
        # decision is made NOT to implement a wait loop for DEPLOYMENT state
        return True

    def change_log_level(self, level_param: EnumParameterType) -> bool:
        """ Change the logger level for the local **Supvisors** instance.
        If **Supvisors** logger is configured as ``AUTO``, this will impact the Supervisor logger too.

        :param Union[str, int] level_param: the new logger level, as a string or as a value.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ``Faults.INCORRECT_PARAMETERS`` if ``level_param`` is unknown to **Supervisor**.
        """
        level = self._get_logger_level(level_param)
        self.logger.warn(f'RPCInterface.change_log_level: {LOG_LEVELS_BY_NUM[level]}')
        self.logger.level = level
        for handler in self.logger.handlers:
            handler.level = level
        return True

    # utilities
    def _get_starting_strategy(self, strategy: EnumParameterType) -> StartingStrategies:
        """ Check if the strategy given can fit to a StartingStrategies enum. """
        return self._get_strategy(strategy, StartingStrategies)

    def _get_conciliation_strategy(self, strategy: EnumParameterType) -> ConciliationStrategies:
        """ Check if the strategy given can fit to a ConciliationStrategies enum. """
        return self._get_strategy(strategy, ConciliationStrategies)

    def _get_strategy(self, strategy: EnumParameterType, enum_klass: EnumClassType) -> EnumType:
        """ Check if the strategy given can fit to string or value of the StartingStrategies enum. """
        # check by string
        if type(strategy) is str:
            try:
                return enum_klass[strategy]
            except KeyError:
                self.logger.error(f'RPCInterface._get_strategy: invalid string for {enum_klass} ({strategy})')
                raise RPCError(Faults.INCORRECT_PARAMETERS,
                               f'invalid {enum_klass}: {strategy} (string expected in {[x.name for x in enum_klass]})')
        # check by value
        if type(strategy) is int:
            try:
                return enum_klass(strategy)
            except ValueError:
                self.logger.error(f'RPCInterface._get_strategy: invalid integer for {enum_klass} ({strategy})')
                raise RPCError(Faults.INCORRECT_PARAMETERS,
                               f'incorrect strategy: {strategy} (integer expected in {[x.value for x in enum_klass]}')
        # other types are wrong
        self.logger.error(f'RPCInterface._get_strategy: invalid {enum_klass} ({strategy})')
        raise RPCError(Faults.INCORRECT_PARAMETERS, f'invalid {enum_klass}: {strategy} (string or integer expected)')

    @staticmethod
    def get_logger_levels() -> Dict[LevelsByName, str]:
        """ Return a dictionary of Supervisor Logger levels.

        :return: the Supervisor Logger levels
        """
        return {level: desc
                for desc, level in LevelsByDescription.__dict__.items()
                if not desc.startswith('_')}

    def _get_logger_level(self, level_param: EnumParameterType) -> int:
        """ Check if the logger level fits to Supervisor Logger levels.
        The function returns a Logger level as defined in the LevelsByName class of the module ``supervisor.loggers``.

        :param level_param: the logger level to be checked, as string or integer.
        :return: the checked logger level as integer.
        """
        # check by string
        if type(level_param) is str:
            level = getLevelNumByDescription(level_param.lower())
            if level is None:
                self.logger.error(f'RPCInterface._get_logger_level: invalid string for logger level={level_param}')
                values = list(RPCInterface.get_logger_levels().values())
                raise RPCError(Faults.INCORRECT_PARAMETERS,
                               f'invalid logger level: {level_param} (string expected in {values})')
            return level
        # check by integer
        if type(level_param) is int:
            if level_param not in RPCInterface.get_logger_levels():
                self.logger.error(f'RPCInterface._get_logger_level: invalid integer logger level={level_param}')
                values = list(RPCInterface.get_logger_levels().keys())
                raise RPCError(Faults.INCORRECT_PARAMETERS,
                               f'invalid logger level: {level_param} (integer expected in {values})')
            return level_param
        # other types are wrong
        self.logger.error(f'RPCInterface._get_logger_level: invalid logger level={level_param}')
        raise RPCError(Faults.INCORRECT_PARAMETERS, f'invalid logger level: {level_param} (string or integer expected)')

    def _check_from_deployment(self) -> None:
        """ Raises a SupvisorsFaults.BAD_SUPVISORS_STATE exception if Supvisors' state is in INITIALIZATION. """
        self._check_state([SupvisorsStates.DEPLOYMENT,
                           SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION,
                           SupvisorsStates.RESTARTING, SupvisorsStates.SHUTTING_DOWN])

    def _check_operating_conciliation(self) -> None:
        """ Raises a SupvisorsFaults.BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in OPERATION or
        CONCILIATION. """
        self._check_state([SupvisorsStates.OPERATION, SupvisorsStates.CONCILIATION])

    def _check_operating(self) -> None:
        """ Raises a SupvisorsFaults.BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in OPERATION. """
        self._check_state([SupvisorsStates.OPERATION])

    def _check_conciliation(self) -> None:
        """ Raises a SupvisorsFaults.BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in OPERATION. """
        self._check_state([SupvisorsStates.CONCILIATION])

    def _check_state(self, states) -> None:
        """ Raises a SupvisorsFaults.BAD_SUPVISORS_STATE exception if Supvisors' state is NOT in one of the states. """
        if self.supvisors.fsm.state not in states:
            raise RPCError(SupvisorsFaults.BAD_SUPVISORS_STATE.value,
                           f'Supvisors (state={self.supvisors.fsm.state.name}) not in state'
                           f' {[state.name for state in states]} to perform request')

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
            message = f'application {application_name} unknown to Supvisors'
            self.logger.error(f'RPCInterface._get_application: {message}')
            raise RPCError(Faults.BAD_NAME, message)

    def _get_process(self, application: ApplicationStatus, process_name: str):
        """ Return the ProcessStatus corresponding to process_name in application.
        A BAD_NAME exception is raised if the process is not found. """
        try:
            return application.processes[process_name]
        except KeyError:
            message = f'process={process_name} unknown in application={application.application_name}'
            self.logger.error(f'RPCInterface._get_process: {message}')
            raise RPCError(Faults.BAD_NAME, message)

    @staticmethod
    def _get_internal_process_rules(process):
        """ Return a dictionary with the rules of the process. """
        result = process.rules.serial()
        result.update({'application_name': process.application_name, 'process_name': process.process_name})
        return result

    def _get_local_info(self, info):
        """ Create a payload from Supervisor process info. """
        sub_info = extract_process_info(info)
        # transform now from int to float
        sub_info['now'] *= 1.0
        # add program-related information for internal purpose
        # add startsecs, stopwaitsecs and extra_args values taken from Supervisor internal model
        process_name = info['name']
        namespec = make_namespec(info['group'], process_name)
        option_names = 'startsecs', 'stopwaitsecs', 'extra_args', 'disabled'
        options = self.supvisors.supervisor_data.get_process_config_options(namespec, option_names)
        sub_info.update(options)
        # add program and process_index taken from SupvisorsServerOptions
        srv_options = self.supvisors.server_options
        sub_info['program_name'] = srv_options.processes_program[process_name]
        sub_info['process_index'] = srv_options.process_indexes[process_name]
        return sub_info
