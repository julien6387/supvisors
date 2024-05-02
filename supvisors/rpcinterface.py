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

import traceback
from typing import Callable, NoReturn, Optional, Type, Union

from supervisor.http import NOT_DONE_YET
from supervisor.loggers import Logger, LevelsByName, LevelsByDescription, getLevelNumByDescription, LOG_LEVELS_BY_NUM
from supervisor.options import make_namespec, split_namespec, VERSION
from supervisor.xmlrpc import Faults, RPCError

from . import __version__
from .application import ApplicationStatus
from .process import ProcessStatus
from .strategy import get_supvisors_instance, conciliate_conflicts
from .ttypes import *
from .utils import extract_process_info


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
    if process and process.supvisors_config.program_config.disabled:
        raise RPCError(SupvisorsFaults.DISABLED.value, name)
    # call normal behavior
    # original method has been renamed on-the-fly as _startProcess
    return self._startProcess(name, wait)


class RPCInterface:
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
        self.logger.info(f'RPCInterface: using Supvisors={__version__} Supervisor={VERSION}')

    @property
    def logger(self) -> Logger:
        """ Get the Supvisors logger. """
        return self.supvisors.logger

    # RPC Status methods
    def get_api_version(self) -> str:
        """ Return the version of the RPC API used by **Supvisors**.

        :return: the **Supvisors** version.
        :rtype: str
        """
        self.logger.blather('RPCInterface.get_api_version: do NOT make it static as it breaks the RPC Interface')
        return __version__

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

            * auto-fencing: Supvisors instance isolation if it becomes inactive ;
            * starting: used in the ``DISTRIBUTION`` state to start applications ;
            * conciliation: used in the ``CONCILIATION`` state to conciliate conflicts.

        :return: a structure containing information about the strategies applied.
        :rtype: dict[str, Any]
        """
        options = self.supvisors.options
        return {'auto-fencing': options.auto_fence,
                'starting': options.starting_strategy.name,
                'conciliation': options.conciliation_strategy.name}

    def get_statistics_status(self) -> Payload:
        """ Get information about the statistics collection status in **Supvisors**:

            * host_stats: True if the host statistics are collected ;
            * process_stats: True if the process statistics are collected ;
            * collecting_period: the minimum interval between 2 samples of the same statistics type.

        :return: a structure containing information about the statistics collected.
        :rtype: dict[str, Any]
        """
        has_collector = self.supvisors.stats_collector is not None
        options = self.supvisors.options
        return {'host_stats': options.host_stats_enabled and has_collector,
                'process_stats': options.process_stats_enabled and has_collector,
                'collecting_period': options.collecting_period}

    def get_all_instances_info(self) -> PayloadList:
        """ Get information about all **Supvisors** instances.

        :return: a list of structures containing information about all **Supvisors** instances.
        :rtype: list[dict[str, Any]]
        """
        return [self.get_instance_info(identifier)[0]
                for identifier in sorted(self.supvisors.mapper.instances)]

    def get_instance_info(self, identifier: str) -> PayloadList:
        """ Get information about the **Supvisors** instances identified by ``identifier`` (Supvisors identifier,
        Supervisor identifier or Supvisors stereotype).

        This method can return multiple results if a **Supvisors** stereotype is used as parameter.

        :param str identifier: the identifier of the Supvisors instance where the Supervisor daemon is running.
        :return: a structure containing information about the **Supvisors** instance.
        :rtype: list[dict[str, Any]].
        :raises RPCError: with code ``Faults.BAD_NAME`` if ``identifier`` is unknown to **Supvisors**.
        """
        identifiers = self.supvisors.mapper.filter([identifier])
        if not identifiers:
            self._raise(Faults.BAD_NAME, 'get_instance_info',
                        f'identifier={identifier} is unknown to Supvisors')
        return [self.supvisors.context.instances[identifier].serial()
                for identifier in identifiers]

    def get_all_applications_info(self) -> PayloadList:
        """ Get information about all applications managed in **Supvisors**.

        :return: a list of structures containing information about all applications.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in
            ``INITIALIZATION`` state.
        """
        self._check_from_distribution()
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
        self._check_from_distribution()
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
        self._check_from_distribution()
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
        self._check_from_distribution()
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
        self._check_from_distribution()
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

    def get_all_inner_process_info(self, identifier: str) -> PayloadList:
        """ Get Supvisors internal information related to the processes declared on the Supvisors instance.
        Mainly used for debug purpose.

        :param str identifier: the identifier of the Supvisors instance where the Supervisor daemon is running.
        :return: a list of structures containing information about the processes.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code ``Faults.BAD_NAME`` if ``identifier`` is unknown to **Supvisors**.
        """
        identifiers = self.supvisors.mapper.filter([identifier])
        if not identifiers:
            self._raise(Faults.BAD_NAME, 'get_inner_process_info',
                        f'identifier={identifier} is unknown to Supvisors')
        # no need to check if the process info_map has an entry for the Supviors instance
        # because it would not make sense if it didn't
        return [proc.info_map[ident]
                for ident in identifiers
                for proc in self.supvisors.context.instances[ident].processes.values()]

    def get_inner_process_info(self, identifier: str, namespec: str) -> PayloadList:
        """ Get Supvisors internal information related to the processes corresponding to namespec and declared
        on the Supvisors instance.
        Mainly used for debug purpose.

        :param str identifier: the identifier of the Supvisors instance where the Supervisor daemon is running.
        :param str namespec: the process namespec (``name``, ``group:name``).
        :return: a structure containing information about the process.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code ``Faults.BAD_NAME`` if ``identifier`` is unknown to **Supvisors**.
        :raises RPCError: with code ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors**.
        :raises RPCError: with code ``Faults.FAILED`` if no handshake has been done with ``identifier``.
        """
        identifiers = self.supvisors.mapper.filter([identifier])
        if not identifiers:
            self._raise(Faults.BAD_NAME, 'get_inner_process_info',
                        f'identifier={identifier} is unknown to Supvisors')
        application, process = self._get_application_process(namespec)
        try:
            # namespec is a single process
            if process:
                return [process.info_map[ident]
                        for ident in identifiers]
            # namespec is a homogeneous group
            return [proc.info_map[ident]
                    for ident in identifiers
                    for proc in self.supvisors.context.instances[ident].processes.values()
                    if proc.application_name == application.application_name]
        except KeyError:
            self._raise(Faults.FAILED, 'get_inner_process_info', f'{namespec} unknown on {identifier}')

    def get_process_rules(self, namespec: str) -> PayloadList:
        """ Get the rules used to start / stop the process named ``namespec``.

        :param str namespec: the process namespec (``name``, ``group:name``, or ``group:*``).
        :return: a list of structures containing the rules.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still in ``INITIALIZATION`` state ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors**.
        """
        self._check_from_distribution()
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
        self._check_from_distribution()
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
            ``Faults.ABNORMAL_TERMINATION`` if the internal start request failed ;
            ``Faults.NOT_RUNNING`` if ``application_name`` could not be started.
        """
        self.logger.trace(f'RPCInterface.start_application: strategy={strategy} application={application_name}'
                          f' wait={wait}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check application name
        application = self._get_application(application_name)
        # check application is managed
        if application_name not in self.supvisors.context.get_managed_applications():
            self._raise(SupvisorsFaults.NOT_MANAGED.value, 'start_application', application_name)
        # check application is not already RUNNING
        if application.state != ApplicationStates.STOPPED:
            self._raise(Faults.ALREADY_STARTED, 'start_application', application_name)
        # if impossible due to a lack of resources, second try without optional
        # return false if still impossible
        self.supvisors.starter.start_application(strategy_enum, application)
        in_progress = self.supvisors.starter.in_progress()
        self.logger.debug(f'RPCInterface.start_application: {application_name} in_progress={in_progress}')
        if not in_progress:
            # the job has not been queued. something wrong happened (lack of resources ?)
            self._raise(Faults.ABNORMAL_TERMINATION, 'start_application', f'failed to start {application_name}')
        # wait until application fully RUNNING or (failed)
        if wait and in_progress:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check starter
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                if application.state != ApplicationStates.RUNNING:
                    self._raise(Faults.NOT_RUNNING, 'start_application', application_name)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return in_progress

    def test_start_application(self, strategy: EnumParameterType, application_name: str) -> PayloadList:
        """ Return a distribution prediction for a start of the *Managed* application named ``application_name``
        iaw the strategy and the rules file.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str application_name: the name of the application.
        :return: a list of structures with the predicted distribution of the application processes.
        :rtype: list[dict[str, Any]]
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if ``application_name`` is unknown to **Supvisors** ;
            ``SupvisorsFaults.NOT_MANAGED`` if the application is not *Managed* in **Supvisors** ;
            ``Faults.ALREADY_STARTED`` if the application is ``STARTING``, ``STOPPING`` or ``RUNNING``.
        """
        self.logger.trace(f'RPCInterface.test_start_application: strategy={strategy} application={application_name}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check application name
        application = self._get_application(application_name)
        # check application is managed
        if application_name not in self.supvisors.context.get_managed_applications():
            self._raise(SupvisorsFaults.NOT_MANAGED.value, 'test_start_application', application_name)
        # check application is not already RUNNING
        if application.state != ApplicationStates.STOPPED:
            self._raise(Faults.ALREADY_STARTED, 'test_start_application', application_name)
        return self.supvisors.starter_model.test_start_application(strategy_enum, application)

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
            ``Faults.NOT_RUNNING`` if ``application_name`` is already stopped ;
            ``Faults.STILL_RUNNING`` if ``application_name`` could not be stopped.
        """
        self.logger.trace(f'RPCInterface.stop_application: application={application_name} wait={wait}')
        self._check_operating_conciliation()
        # check application name
        application = self._get_application(application_name)
        # check application is managed
        if application_name not in self.supvisors.context.get_managed_applications():
            self._raise(SupvisorsFaults.NOT_MANAGED.value, 'stop_application', application_name)
        # check application is not already STOPPED
        if not application.has_running_processes():
            self._raise(Faults.NOT_RUNNING, 'stop_application', f'failed to stop {application_name}')
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
                    self._raise(Faults.STILL_RUNNING, 'stop_application', application_name)
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
            ``Faults.ABNORMAL_TERMINATION`` if the internal restart request failed ;
            ``Faults.NOT_RUNNING`` if `application_name`` could not be restarted.
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
            self._raise(Faults.ABNORMAL_TERMINATION, 'restart_application', f'failed to restart {application_name}')
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
                    self._raise(Faults.NOT_RUNNING, 'restart_application', application_name)
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
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to Supvisors or Supervisor ;
            ``SupvisorsFaults.DISABLED`` if process is *disabled* ;
            ``Faults.ALREADY_STARTED`` if process is ``RUNNING`` ;
            ``Faults.ABNORMAL_TERMINATION`` if process could not be started.
        """
        # WARN: do NOT check OPERATION (it is used internally in DISTRIBUTION state)
        _, process = self._get_application_process(namespec)
        # update command line in process config with extra_args
        try:
            self.supvisors.supervisor_data.update_extra_args(process.namespec, extra_args)
        except KeyError:
            # process is unknown to the local Supervisor
            # this is unexpected as Supvisors checks the configuration before it sends this request
            self._raise(Faults.BAD_NAME, 'start_args', f'namespec={namespec} unknown to Supervisor')
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
            ``Faults.ABNORMAL_TERMINATION`` if the internal start request failed ;
            ``Faults.NOT_RUNNING`` if ``namespec`` could not be started.
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
                self._raise(Faults.ALREADY_STARTED, 'start_process', process.namespec)
        # start all processes
        for process in processes:
            self.supvisors.starter.start_process(strategy_enum, process, extra_args)
        in_progress = self.supvisors.starter.in_progress()
        self.logger.debug(f'RPCInterface.start_process: {process.namespec} in_progress={in_progress}')
        if not in_progress:
            # one of the jobs has not been queued. something wrong happened (lack of resources ?)
            self._raise(Faults.ABNORMAL_TERMINATION, 'start_process', f'failed to start {namespec}')
        # wait until application fully RUNNING or failed
        if wait:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check starter
                if self.supvisors.starter.in_progress():
                    return NOT_DONE_YET
                proc_errors = []
                for proc in processes:
                    if proc.stopped():
                        proc_errors.append(proc.namespec)
                if proc_errors:
                    self._raise(Faults.NOT_RUNNING, 'start_process', f'processes={proc_errors}')
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return True

    def test_start_process(self, strategy: EnumParameterType, namespec: str) -> WaitReturnType:
        """ Return a distribution prediction for starting the processes corresponding to the namspec
        iaw the strategy and the rules file.

        :param StartingStrategies strategy: the strategy used to choose a **Supvisors** instance,
            as a string or as a value.
        :param str namespec: the process namespec (``name``,``group:name``, or ``group:*``).
        :return: a list of structures with the predicted distribution of the processes.
        :rtype: list[dict[str, Any]].
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.INCORRECT_PARAMETERS`` if ``strategy`` is unknown to **Supvisors** ;
            ``Faults.BAD_NAME`` if ``namespec`` is unknown to **Supvisors** ;
            ``Faults.ALREADY_STARTED`` if process is in a running state.
        """
        self.logger.trace(f'RPCInterface.test_start_process: namespec={namespec} strategy={strategy}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # check names
        application, process = self._get_application_process(namespec)
        processes = [process] if process else application.processes.values()
        # check processes are not already running
        for process in processes:
            if process.running():
                self._raise(Faults.ALREADY_STARTED, 'test_start_process', process.namespec)
        # start all processes
        return self.supvisors.starter_model.test_start_processes(strategy_enum, processes)

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
            ``Faults.FAILED`` if no stopped process found matching ``regex`` in **Supvisors** ;
            ``Faults.ABNORMAL_TERMINATION`` if the internal start request failed ;
            ``Faults.NOT_RUNNING`` if ``namespec`` could not be started.
        """
        self.logger.trace(f'RPCInterface.start_any_process: regex={regex} strategy={strategy} extra_args="{extra_args}"'
                          f' wait={wait}')
        self._check_operating()
        strategy_enum = self._get_starting_strategy(strategy)
        # get the processes whose namespec matches the regex and that are not running
        processes = self.supvisors.context.find_runnable_processes(regex)
        # get the first process that allows a starting iaw the strategy, rules and current distribution
        namespec = None
        load_request_map = self.supvisors.starter.get_load_requests()
        for process in processes:
            if get_supvisors_instance(self.supvisors, strategy_enum, process.possible_identifiers(),
                                      process.rules.expected_load, load_request_map):
                namespec = process.namespec
                break
        if not namespec:
            self._raise(Faults.FAILED, 'start_any_process', f'no candidate process matching "{regex}"')
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
            ``Faults.NOT_RUNNING`` if ``namespec`` is already stopped ;
            ``Faults.STILL_RUNNING`` if ``namespec`` could not be stopped.
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
            self._raise(Faults.NOT_RUNNING, 'stop_process', f'{namespec} already stopped')
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
                        proc_errors.append(proc.namespec)
                if proc_errors:
                    self._raise(Faults.STILL_RUNNING, 'stop_process', f'processes={proc_errors}')
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
            ``Faults.ABNORMAL_TERMINATION`` if the internal restart request failed ;
            ``Faults.NOT_RUNNING`` if ``namespec`` could not be restarted.
        """
        self.logger.trace(f'RPCInterface.restart_process: strategy={strategy} process={namespec} args={extra_args}'
                          f' wait={wait}')
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
            self._raise(Faults.ABNORMAL_TERMINATION, 'restart_process', f'failed to restart {namespec}')
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
                        proc_errors.append(proc.namespec)
                if proc_errors:
                    self._raise(Faults.NOT_RUNNING, 'restart_process', f'processes={proc_errors}')
                return True
            onwait.delay = 0.5
            onwait.waitstop = True
            return onwait  # deferred
        return True

    def _check_process_insertion(self, namespecs: NameList):
        """ Following a numprocs increase, check that the processes have been added to Supvisors.

        :param namespecs: the namespecs of the new processes.
        :return: None
        """
        self.logger.debug(f'RPCInterface._check_process_insertion: new processes={namespecs}')
        local_identifier = self.supvisors.mapper.local_identifier
        proc_errors = []
        for namespec in namespecs:
            try:
                proc = self.supvisors.context.get_process(namespec)
                assert local_identifier in proc.info_map
            except (AssertionError, KeyError):
                proc_errors.append(namespec)
        if proc_errors:
            self._raise(Faults.FAILED, '_check_process_insertion', f'processes={proc_errors}')

    def _check_process_deletion(self, namespecs: NameList) -> None:
        """ Following a numprocs decrease, check that the processes have been removed from Supvisors.

        :param namespecs: the namespecs of the new processes.
        :return: None
        """
        self.logger.debug(f'RPCInterface._check_process_deletion: stale processes={namespecs}')
        local_identifier = self.supvisors.mapper.local_identifier
        proc_errors = []
        for namespec in namespecs:
            try:
                proc = self.supvisors.context.get_process(namespec)
                if local_identifier in proc.info_map:
                    proc_errors.append(namespec)
            except KeyError:
                # process may have been deleted if there is no more Supervisor instance supporting it
                self.logger.debug(f'RPCInterface._check_process_deletion: process={namespec} has been deleted')
        if proc_errors:
            self._raise(Faults.FAILED, '_check_process_deletion', f'processes={proc_errors}')

    def _decrease_numprocs(self, namespecs: NameList, wait: bool) -> WaitReturnType:
        """ Following a call to update_numprocs, a number of processes have to be stopped and removed.

        :param namespecs: the namespecs of the processes to stop and remove.
        :param bool wait: if ``True``, wait for the confirmation that processes have been removed from Supvisors.
        :return: a callable for the deferred actions.
        :raises RPCError: with code ``Faults.STILL_RUNNING`` if one of ``namespecs`` cannot be stopped.
        """
        # if the value is lower than the current one, processes must be stopped before they are deleted
        # the corresponding processes will be removed from Supervisors once they reach a non-running state
        self.logger.debug(f'RPCInterface._decrease_numprocs: obsolete processes={namespecs}')
        local_identifier = self.supvisors.mapper.local_identifier
        processes_to_stop = list(filter(lambda x: x.running_on(local_identifier),
                                        [self.supvisors.context.get_process(del_namespec)
                                         for del_namespec in namespecs]))
        for process in processes_to_stop:
            self.logger.debug(f'RPCInterface._decrease_numprocs: stopping process={process.namespec}')
            self.supvisors.stopper.stop_process(process, [local_identifier], False)
        self.supvisors.stopper.next()
        # final check depends on wait parameter
        if not wait:
            # perform a basic check on processes that were already stopped
            # they have been already removed from Supvisors and Supervisor
            processes_to_check = [proc for proc in namespecs
                                  if proc not in processes_to_stop]
            self._check_process_deletion(processes_to_check)
        else:
            def onwait() -> RPCInterface.OnWaitReturnType:
                # check stopper
                if self.supvisors.stopper.in_progress():
                    return NOT_DONE_YET
                # when stopper is done, check that the processes are not running anymore
                proc_errors = []
                for proc in processes_to_stop:
                    if proc.running():
                        proc_errors.append(proc.namespec)
                # complete removal in Supervisor
                if proc_errors:
                    self._raise(Faults.STILL_RUNNING, '_decrease_numprocs', f'processes={proc_errors}')
                # confirm that the removal is done in Supvisors
                self._check_process_deletion(namespecs)
                return True

            onwait.delay = 0.5
            return onwait  # deferred
        return True

    def update_numprocs(self, program_name: str, numprocs: int, wait: bool = True, lazy: bool = False) -> WaitReturnType:
        """ Update dynamically the numprocs of the program.
        Implementation of Supervisor issue #177 - Dynamic numproc change.

        When the number of processes decreases:
            - the processes in excess are immediately stopped if lazy is False ;
            - the processes in excess are kept in Supervisor as long as they're still running if lazy is True.

        :param str program_name: the program name, as found in the section of the Supervisor configuration files.
            Programs, FastCGI programs and event listeners are supported.
        :param int numprocs: the new numprocs value (must be strictly positive).
        :param bool wait: if ``True`` and the numprocs value decreases, wait for the processes in excess to be stopped.
        :param bool lazy: if ``True``, use the lazy mode when decreasing the program numprocs.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``OPERATION`` ;
            ``Faults.BAD_NAME`` if ``program_name`` is unknown to **Supvisors** ;
            ``Faults.INCORRECT_PARAMETERS`` if ``numprocs`` is not a strictly positive integer ;
            ``SupvisorsFaults.NOT_APPLICABLE`` if the program configuration does not support numprocs ;
            ``Faults.STILL_RUNNING`` if one process corresponding to ``program_name`` cannot be stopped.
        """
        self.logger.trace(f'RPCInterface.update_numprocs: program={program_name} numprocs={numprocs}')
        self._check_operating()
        # test that program_name is known to the ServerOptions
        if program_name not in self.supvisors.server_options.program_configs:
            self._raise(Faults.BAD_NAME, 'update_numprocs', f'program={program_name} unknown to Supvisors')
        # test that numprocs is strictly positive
        try:
            value = int(numprocs)
            assert value > 0
        except (ValueError, AssertionError):
            self._raise(Faults.INCORRECT_PARAMETERS, 'update_numprocs',
                        f'program={program_name} incorrect numprocs={numprocs}',
                        'integer > 0 expected')
        try:
            add_namespecs, del_namespecs = self.supvisors.supervisor_updater.update_numprocs(program_name, value)
        except ValueError:
            self.logger.error(f'RPCInterface.update_numprocs: {traceback.format_exc()}')
            self._raise(SupvisorsFaults.NOT_APPLICABLE.value, 'update_numprocs',
                        f'numprocs not applicable to program={program_name}')
        # use different methods for the next activities
        if add_namespecs:
            self._check_process_insertion(add_namespecs)
            return True
        if del_namespecs:
            if lazy:
                return True
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
        if program_name not in self.supvisors.server_options.program_configs:
            self._raise(Faults.BAD_NAME, 'enable', f'program={program_name} unknown to Supvisors')
        # re-enable the corresponding process to be started
        self.supvisors.supervisor_updater.enable_program(program_name)
        if wait:
            # get corresponding subprocesses
            subprocesses = self.supvisors.server_options.get_subprocesses(program_name)
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
            ``Faults.BAD_NAME`` if ``program_name`` is unknown to **Supvisors** ;
            ``Faults.STILL_RUNNING`` if at least one process corresponding to ``program_name`` cannot be stopped.
        """
        self.logger.trace(f'RPCInterface.disable: program_name={program_name}')
        self._check_operating()
        # test that program_name is known to the ServerOptions
        if program_name not in self.supvisors.server_options.program_configs:
            self._raise(Faults.BAD_NAME, 'disable', f'program={program_name} unknown to Supvisors')
        # whatever they are already stopped or not, it is safe to disable the processes right now
        self.supvisors.supervisor_updater.disable_program(program_name)
        # get corresponding subprocesses
        subprocesses = self.supvisors.server_options.get_subprocesses(program_name)
        # stop all running processes related to the program
        self.logger.debug(f'RPCInterface.disable: program_name={program_name} processes={subprocesses}')
        local_identifier = self.supvisors.mapper.local_identifier
        processes_to_stop = list(filter(lambda x: x.running_on(local_identifier),
                                        [self._get_application_process(namespec)[1]
                                         for namespec in subprocesses]))
        self.logger.debug(f'RPCInterface.disable: processes_to_stop={processes_to_stop}')
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
                    self.logger.debug('RPCInterface.disable: stopper done')
                    onwait.waitstop = False
                    # report errors if any
                    proc_errors = []
                    for proc in processes_to_stop:
                        if proc.running():
                            proc_errors.append(proc.namespec)
                    if proc_errors:
                        self._raise(Faults.STILL_RUNNING, 'disable', f'processes={proc_errors}')
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
        """ Triggers the whole starting sequence by going back to the DISTRIBUTION state.

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
                # first wait for DISTRIBUTION state
                if onwait.wait_state == SupvisorsStates.DISTRIBUTION:
                    if self.supvisors.fsm.state == SupvisorsStates.DISTRIBUTION:
                        onwait.wait_state = SupvisorsStates.OPERATION
                    return NOT_DONE_YET
                else:
                    # when reached, wait for OPERATION state
                    if self.supvisors.fsm.state != SupvisorsStates.OPERATION:
                        return NOT_DONE_YET
                    return True

            onwait.delay = 0.5
            onwait.wait_state = SupvisorsStates.DISTRIBUTION
            return onwait  # deferred
        return True

    def restart(self) -> bool:
        """ Stops all applications and restart **Supvisors** through all Supervisor daemons.

        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ```SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still
            in state ``INITIALIZATION`` or has no Master instance to perform the request.
        """
        self._check_from_distribution()
        self.supvisors.fsm.on_restart()
        return True

    def shutdown(self) -> bool:
        """ Stops all applications and shut down **Supvisors** through all Supervisor daemons.

        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ```SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is still
            in state ``INITIALIZATION`` or has no Master instance to perform the request.
        """
        self._check_from_distribution()
        self.supvisors.fsm.on_shutdown()
        return True

    def end_sync(self, master: str = '') -> bool:
        """ Ends the synchronization phase on the basis of the known situation.

        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code:
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if **Supvisors** is not in state ``INITIALIZATION`` ;
            ``SupvisorsFaults.BAD_SUPVISORS_STATE`` if the synchronization is ending (master elected) ;
            ``SupvisorsFaults.NOT_APPLICABLE`` if the synchro_options does not include ``USER`` ;
            ``Faults.BAD_NAME`` if master is an unknown Supvisors identifier ;
            ``Faults.INCORRECT_PARAMETERS`` if master is resolved in multiple Supvisors identifiers ;
            ``Faults.NOT_RUNNING`` if the selected Master Supvisors instance is not in state ``RUNNING``.
        """
        self._check_state([SupvisorsStates.INITIALIZATION])
        if self.supvisors.context.master_identifier:
            self._raise(SupvisorsFaults.BAD_SUPVISORS_STATE.value, 'end_sync', 'Supvisors synchronization ending')
        if SynchronizationOptions.USER not in self.supvisors.options.synchro_options:
            self._raise(SupvisorsFaults.NOT_APPLICABLE.value, 'end_sync', 'USER expected in synchro_options')
        if master:
            identifiers = self.supvisors.mapper.filter([master])
            if not identifiers:
                self._raise(Faults.BAD_NAME, 'end_sync', f'unknown Supvisors identifier={master}')
            if len(identifiers) > 1:
                self._raise(Faults.INCORRECT_PARAMETERS, 'end_sync',
                            f'multiple identifiers={identifiers} found for Supvisors master={master}')
            master = identifiers[0]
            status = self.supvisors.context.instances[master]
            if status.state != SupvisorsInstanceStates.RUNNING:
                self._raise(Faults.NOT_RUNNING, 'end_sync',
                            f'Supvisors instance={master} is not RUNNING ({status.state.name})')
        # checks passed so trigger the request
        self.supvisors.fsm.on_end_sync(master)
        # decision is made NOT to implement a wait loop for DISTRIBUTION state
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

    def enable_host_statistics(self, enable_host: bool) -> bool:
        """ Override the host statistics option for the local **Supvisors** instance.

        :param bool enable_host: if True/False and psutil installed, enable/disable host statistics collection.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ``SupvisorsFaults.NOT_INSTALLED`` if ``psutil`` is not installed.
        """
        if not self.supvisors.stats_collector:
            self._raise(SupvisorsFaults.NOT_INSTALLED.value, 'enable_host_statistics', 'psutil not installed')
        # update the host statistics collection status
        self.supvisors.options.host_stats_enabled = enable_host
        self.supvisors.stats_collector.enable_host_statistics(enable_host)
        return True

    def enable_process_statistics(self, enable_process: bool) -> bool:
        """ Override the process statistics option for the local **Supvisors** instance.

        :param bool enable_process: if True/False and psutil installed, enable/disable process statistics collection.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ``SupvisorsFaults.NOT_INSTALLED`` if ``psutil`` is not installed.
        """
        if not self.supvisors.stats_collector:
            self._raise(SupvisorsFaults.NOT_INSTALLED.value, 'enable_process_statistics', 'psutil not installed')
        # update the process statistics collection status
        self.supvisors.options.process_stats_enabled = enable_process
        self.supvisors.stats_collector.enable_process_statistics(enable_process)
        return True

    def update_collecting_period(self, collecting_period: float) -> bool:
        """ Override the statistics period option for the local **Supvisors** instance.

        :param float collecting_period: the minimum interval between 2 samples of the same statistics type.
        :return: always ``True`` unless error.
        :rtype: bool
        :raises RPCError: with code ``SupvisorsFaults.NOT_INSTALLED`` if ``psutil`` is not installed.
        """
        if not self.supvisors.stats_collector:
            self._raise(SupvisorsFaults.NOT_INSTALLED.value, 'update_collecting_period', 'psutil not installed')
        self.supvisors.options.collecting_period = collecting_period
        self.supvisors.stats_collector.update_collecting_period(collecting_period)
        return True

    # utilities
    def _raise(self, code: int, func: str, message: str, complement: Optional[str] = None) -> NoReturn:
        """ Log the error and raise the exception. """
        self.logger.error(f'RPCInterface.{func}: {message}')
        complete_message = message
        if complement:
            complete_message += f' - {complement}'
        raise RPCError(code, f'{complete_message}')

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
                self._raise(Faults.INCORRECT_PARAMETERS, '_get_strategy',
                            f'invalid {enum_klass} value={strategy}',
                            f'string expected in {[x.name for x in enum_klass]}')
        # check by value
        if type(strategy) is int:
            try:
                return enum_klass(strategy)
            except ValueError:
                self._raise(Faults.INCORRECT_PARAMETERS, '_get_strategy',
                            f'invalid {enum_klass} value={strategy}',
                            f'integer expected in {[x.value for x in enum_klass]}')
        # other types are wrong
        self._raise(Faults.INCORRECT_PARAMETERS, '_get_strategy',
                    f'invalid {enum_klass} value={strategy} type={type(strategy)}',
                    'type string or integer expected')

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
                values = list(RPCInterface.get_logger_levels().values())
                self._raise(Faults.INCORRECT_PARAMETERS, '_get_logger_level',
                            f'invalid logger value={level_param}',
                            f'string expected in {values}')
            return level
        # check by integer
        if type(level_param) is int:
            if level_param not in RPCInterface.get_logger_levels():
                values = list(RPCInterface.get_logger_levels().keys())
                self._raise(Faults.INCORRECT_PARAMETERS, '_get_logger_level',
                            f'invalid logger value={level_param}',
                            f'integer expected in {values}')
            return level_param
        # other types are wrong
        self._raise(Faults.INCORRECT_PARAMETERS, '_get_logger_level',
                    f'invalid logger value={level_param} type={type(level_param)}',
                    'type string or integer expected')

    def _check_from_distribution(self) -> None:
        """ Raises a SupvisorsFaults.BAD_SUPVISORS_STATE exception if Supvisors' state is in INITIALIZATION. """
        self._check_state([SupvisorsStates.DISTRIBUTION,
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
            self._raise(SupvisorsFaults.BAD_SUPVISORS_STATE.value, '_check_state',
                        f'invalid Supvisors state={self.supvisors.fsm.state.name}',
                        f'state expected in {[state.name for state in states]}')

    def _get_application_process(self, namespec: str) -> Tuple[ApplicationStatus, Optional[ProcessStatus]]:
        """ Return the ApplicationStatus and ProcessStatus corresponding to the namespec.
        A BAD_NAME exception is raised if the application or the process is not found. """
        application_name, process_name = split_namespec(namespec)
        application = self._get_application(application_name)
        process = self._get_process(application, process_name) if process_name else None
        return application, process

    def _get_application(self, application_name: str) -> ApplicationStatus:
        """ Return the ApplicationStatus corresponding to the application name.
        A BAD_NAME exception is raised if the application is not found. """
        try:
            return self.supvisors.context.applications[application_name]
        except KeyError:
            self._raise(Faults.BAD_NAME, '_get_application',
                        f'application={application_name} unknown to Supvisors')

    def _get_process(self, application: ApplicationStatus, process_name: str):
        """ Return the ProcessStatus corresponding to process_name in application.
        A BAD_NAME exception is raised if the process is not found. """
        try:
            return application.processes[process_name]
        except KeyError:
            self._raise(Faults.BAD_NAME, '_get_process',
                        f'process={process_name} unknown in application={application.application_name}')

    @staticmethod
    def _get_internal_process_rules(process):
        """ Return a dictionary with the rules of the process. """
        result = process.rules.serial()
        result.update({'application_name': process.application_name,
                       'process_name': process.process_name})
        return result

    def _get_local_info(self, info):
        """ Create a payload from Supervisor process info. """
        # filter useless (for Supvisors) information
        sub_info = extract_process_info(info)
        # add program-related information for internal purpose
        namespec = make_namespec(info['group'], info['name'])
        # add values taken from Supervisor configuration
        process_info = self.supvisors.supervisor_data.get_process_info(namespec)
        sub_info.update(process_info)
        return sub_info
