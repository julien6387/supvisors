.. _xml_rpc:

XML-RPC API
===========

The |Supvisors| XML-RPC API is an extension of the |Supervisor| XML-RPC API.
Detailed information can be found in the
`Supervisor XML-RPC API Documentation <http://supervisord.org/api.html#xml-rpc-api-documentation>`_.

The ``supvisors`` namespace has been added to the ``supervisor`` XML-RPC interface.

The XML-RPC :command:`system.listMethods` provides the list of methods supported for both |Supervisor| and |Supvisors|.

.. code-block:: python

    server.supvisors.getState()

.. important::

    In the following, the namespec refers to the full name of the program, including the group name, as defined in
    |Supervisor|. For example: in :program:`X11:xclock`, ``X11`` is the name of a |Supervisor| group and ``xclock``
    is the name of a |Supervisor| program that is referenced in the group.
    In some cases, it can also refer to all the programs of the group (:program:`X11:*`).


.. automodule:: supvisors.rpcinterface

.. _xml_rpc_status:

Status
------

  .. autoclass:: RPCInterface

        .. automethod:: get_api_version()

        .. automethod:: get_supvisors_state()

            ================== ================= ===========
            Key                Type              Description
            ================== ================= ===========
            'identifier'       ``str``           The |Supvisors| local instance identifier (``host_id:http_port``).
            'nick_identifier'  ``str``           The |Supvisors| local instance nick name, or a copy of the |Supvisors|
                                                 identifier if not set.
            'fsm_statecode'    ``int``           The |Supvisors| state, in [0;8].
            'fsm_statename'    ``str``           The |Supvisors| state as string, in [``'OFF'``, ``'SYNCHRONIZATION'``,
                                                 ``ELECTION``, ``'DISTRIBUTION'``, ``'OPERATION'``, ``'CONCILIATION'``,
                                                 ``'RESTARTING'``, ``'SHUTTING_DOWN'``, ``'FINAL'``].
            'degraded_mode'    ``bool``          True if |Supvisors| is working with missing |Supvisors| instances.
            'discovery_mode'   ``bool``          True if the |Supvisors| discovery mode is activated.
            'starting_jobs'    ``list(str)``     The list of |Supvisors| instances having starting jobs in progress.
            'stopping_jobs'    ``list(str)``     The list of |Supvisors| instances having stopping jobs in progress.
            'instance_states'  ``dict(str,str)`` The state of every |Supvisors| instance, as seen by the local
                                                 |Supvisors| instance.
            ================== ================= ===========

        .. automethod:: get_all_instances_state_modes()

        .. automethod:: get_instance_state_modes()

            ================== ================= ===========
            Key                Type              Description
            ================== ================= ===========
            'identifier'       ``str``           The |Supvisors| instance identifier (``host_id:http_port``).
            'nick_identifier'  ``str``           The |Supvisors| instance nick name, or a copy of the |Supvisors|
                                                 identifier if not set.
            'fsm_statecode'    ``int``           The |Supvisors| state, in [0;8].
            'fsm_statename'    ``str``           The |Supvisors| state as string, in [``'OFF'``, ``'SYNCHRONIZATION'``,
                                                 ``ELECTION``, ``'DISTRIBUTION'``, ``'OPERATION'``, ``'CONCILIATION'``,
                                                 ``'RESTARTING'``, ``'SHUTTING_DOWN'``, ``'FINAL'``].
            'degraded_mode'    ``bool``          True if |Supvisors| is working with missing |Supvisors| instances.
            'discovery_mode'   ``bool``          True if the |Supvisors| discovery mode is activated.
            'starting_jobs'    ``bool``          True if the |Supvisors| instance has starting jobs in progress.
            'stopping_jobs'    ``bool``          True if the |Supvisors| instance has stopping jobs in progress.
            'instance_states'  ``dict(str,str)`` The state of every |Supvisors| instance, as seen by the |Supvisors|
                                                 instance.
            ================== ================= ===========

        .. automethod:: get_master_identifier()

        .. automethod:: get_strategies()

            =================== ========= ===========
            Key                 Type      Description
            =================== ========= ===========
            'auto-fencing'      ``bool``  The application status of the auto-fencing in |Supvisors|.
            'conciliation'      ``str``   The conciliation strategy applied when |Supvisors| is in the ``CONCILIATION``
                                          state.
            'supvisors_failure' ``str``   The strategy used when the initial conditions are not met anymore.
            'starting'          ``str``   The starting strategy applied when |Supvisors| is in the ``DISTRIBUTION``
                                          state.
            =================== ========= ===========

        .. automethod:: get_local_supvisors_info()

            ================== ================= ===========
            Key                Type              Description
            ================== ================= ===========
            'identifier'       ``str``           The |Supvisors| instance identifier (``host_id:http_port``).
            'nick_identifier'  ``str``           The |Supvisors| instance nick name, or a copy of the |Supvisors|
                                                 identifier if not set.
            'host_id'          ``str``           The configured |Supvisors| instance host identifier.
            'http_port'        ``int``           The configured |Supervisor| HTTP port.
            'stereotypes'      ``list(str)``     The stereotypes associated with the |Supvisors| instance configuration.
            'network'          ``dict(str,any)`` The network details of the |Supvisors| instance, with keys in
                                                 [``'fqdn'``, ``'machine_id'``, `'addresses'``].
            'fqdn'             ``str``           The fully-qualified domain name of the |Supvisors| instance.
            'machine_id'       ``str``           The UUID of the node where the |Supvisors| instance is running.
            'addresses'        ``dict(str,any)`` The network interface details, where keys are NIC names (loopback
                                                 excluded), and values are as follows.
            'nic_info'         ``dict(str,str)`` The ``ioctl`` details of the network interface, with keys in
                                                 [``'nic_name'``, ``'ipv4_address'``, `'netmask'``].
            'nic_name'         ``str``           The name of the network interface.
            'ipv4_address'     ``str``           The IPv4 address associated with the network interface.
            'netmask'          ``str``           The netmask associated with the network interface.
            'host_name'        ``str``           The host name given by the ``socket.gethostbyaddr(ipv4_address)``.
            'aliases'          ``list(str)``     The host aliases given by the ``socket.gethostbyaddr(ipv4_address)``.
            'ipv4_addresses'   ``list(str)``     The IPv4 addresses given by the ``socket.gethostbyaddr(ipv4_address)``.
            ================== ================= ===========

        .. automethod:: get_instance_info(identifier)

            ========================= ========= ===========
            Key                       Type      Description
            ========================= ========= ===========
            'identifier'              ``str``   The |Supvisors| instance identifier (``host_id:http_port``).
            'nick_identifier'         ``str``   The |Supervisor| instance identifier, or a copy of the |Supvisors|
                                                identifier if not set.
            'node_name'               ``str``   The name of the node where the |Supvisors| instance is running.
            'port'                    ``int``   The HTTP port of the |Supvisors| instance.
            'statecode'	              ``int``   The |Supvisors| instance state, in [0;5].
            'statename'	              ``str``   The |Supvisors| instance state as string, in [``'SILENT'``, ``'CHECKING'``,
                                                `'CHECKED'``, ``'RUNNING'``, ``'FAILED'``, ``'ISOLATED'``].
            'loading'                 ``int``   The sum of the expected loading of the processes running on the |Supvisors|
                                                instance, in [0;100]%.
            'process_failure'         ``bool``  True if one of the local processes has crashed or has exited unexpectedly.
            'remote_sequence_counter' ``int``   The remote TICK counter, i.e. the number of TICK events received since
                                                the remote |Supvisors| instance is running.
            'remote_mtime'            ``float`` The monotonic time received in the last heartbeat sent by the remote
                                                |Supvisors| instance, in seconds since the remote host started.
            'remote_time'             ``float`` The POSIX time received in the last heartbeat sent by the remote
                                                |Supvisors| instance, in seconds and in the remote reference time.
            'local_sequence_counter'  ``int``   The local TICK counter when the latest TICK was received from the remote
                                                |Supvisors| instance.
            'local_mtime'             ``float`` The monotonic time when the latest TICK was received from the remote
                                                |Supvisors| instance, in seconds since the local host started.
            'local_time'              ``float`` The POSIX time when the latest TICK was received from the remote
                                                |Supvisors| instance, in seconds and in the local reference time.
            ========================= ========= ===========

        .. automethod:: get_all_instances_info()

        .. automethod:: get_application_info(application_name)

            ================== ========= ===========
            Key                Type      Description
            ================== ========= ===========
            'application_name' ``str``   The Application name.
            'statecode'        ``int``   The Application state, in [0;4].
            'statename'        ``str``   The Application state as string, in [``'UNKNOWN'``, ``'STOPPED'``,
                                         ``'STARTING'``, ``'STOPPING'``, ``'RUNNING'``].
            'major_failure'    ``bool``  ``True`` if at least one required process is not started.
            'minor_failure'    ``bool``  ``True`` if at least one optional process could not be started.
            ================== ========= ===========

        .. automethod:: get_all_applications_info()

        .. automethod:: get_process_info(namespec)

            ================== =============== ===========
            Key                Type            Description
            ================== =============== ===========
            'application_name' ``str``         The Application name the process belongs to.
            'process_name'     ``str``         The Process name.
            'statecode'        ``int``         The Process state, in {0, 10, 20, 30, 40, 100, 200, 1000}.
            'statename'        ``str``         The Process state as string, in [``'STOPPED'``, ``'STARTING'``,
                                               ``'RUNNING'``, ``'BACKOFF'``, ``'STOPPING'``, ``'EXITED'``, ``'FATAL'``,
                                               ``'UNKNOWN'``].
            'expected_exit'    ``bool``        A status telling if the process has exited expectedly.
            'last_event_time'  ``float``       The local monotonic time of the last event received for this process,
                                               in seconds.
            'identifiers'      ``list(str)``   The identifiers of all |Supvisors| instances where the process is
                                               running.
            'extra_args'       ``str``         The extra arguments used in the command line of the process.
            ================== =============== ===========

            .. hint::

                The 'expected_exit' status is an answer to the following |Supervisor| request:

                    * `#763 - unexpected exit not easy to read in status or getProcessInfo <https://github.com/Supervisor/supervisor/issues/763>`_

            .. note::

                If there is more than one element in the 'identifiers' list, a process conflict is in progress.


        .. automethod:: get_all_process_info()

        .. automethod:: get_local_process_info(namespec)

            ================== =============== ===========
            Key                Type            Description
            ================== =============== ===========
            'group'            ``str``         The Application name the process belongs to.
            'name'             ``str``         The Process name.
            'state'            ``int``         The Process state, in {0, 10, 20, 30, 40, 100, 200, 1000}.
            'start'            ``int``         The Process start time.
            'start_monotonic'  ``float``       The Process monotonic start time.
            'stop'             ``int``         The Process stop time.
            'stop_monotonic'   ``float``       The Process monotonic stop time.
            'now'              ``float``       The Process current time.
            'now_monotonic'    ``float``       The Process monotonic current time.
            'pid'              ``int``         The UNIX process identifier.
            'startsecs'        ``int``         The configured duration between process STARTING and RUNNING.
            'stopwaitsecs'     ``int``         The configured duration in STOPPING before sending a KILL signal.
            'pid'              ``int``         The UNIX process identifier.
            'extra_args'       ``str``         The extra arguments used in the command line of the process.
            'disabled'         ``bool``        A status telling if the process is disabled.
            'program_name'     ``str``         The program name in |Supervisor| configuration.
            'process_index'    ``int``         The process index in the case of a homogeneous group.
            'has_stdout'       ``bool``        True if a stdout log file is configured in the |Supervisor| program.
            'has_stderr'       ``bool``        True if a stderr log file is configured in the |Supervisor| program.
            ================== =============== ===========

        .. automethod:: get_all_local_process_info()

        .. automethod:: get_inner_process_info()

        .. automethod:: get_all_inner_process_info()

        .. automethod:: get_application_rules(application_name)

            =========================== =============== ===========
            Key                         Type            Description
            =========================== =============== ===========
            'application_name'          ``str``         The Application name.
            'managed'                   ``bool``        The Application managed status in |Supvisors|. When ``False``,
                                                        the following attributes are not provided.
            'distribution'              ``str``         The distribution rule of the Application,
                                                        in [``'ALL_INSTANCES'``, ``'SINGLE_INSTANCE'``,
                                                        ``'SINGLE_NODE'``].
            'identifiers'               ``list(str)``   The identifiers of all |Supvisors| instances where the
                                                        non-fully distributed Application processes can be started,
                                                        provided only if ``distribution`` is not ``ALL_INSTANCES``.
            'start_sequence'            ``int``         The Application starting rank when starting all applications,
                                                        in [0;127].
            'stop_sequence'             ``int``         The Application stopping rank when stopping all applications,
                                                        in [0;127].
            'starting_strategy'         ``str``         The strategy applied when starting Application automatically,
                                                        in [``'CONFIG'``, ``'LESS_LOADED'``, ``'MOST_LOADED'``,
                                                        ``'LOCAL'``, ``'LESS_LOADED_NODE'``, ``'MOST_LOADED_NODE'``].
            'starting_failure_strategy' ``str``         The strategy applied when a process crashes in a starting
                                                        Application, in [``'ABORT'``, ``'STOP'``, ``'CONTINUE'``].
            'running_failure_strategy'  ``str``         The strategy applied when a process crashes in a running
                                                        Application, in [``'CONTINUE'``, ``'RESTART_PROCESS'``,
                                                        ``'STOP_APPLICATION'``, ``'RESTART_APPLICATION'``,
                                                        ``'SHUTDOWN'``, ``'RESTART'``].
            'status_formula'            ``str``         The ``operational_status`` formula set in the Application rule.
            =========================== =============== ===========

        .. automethod:: get_process_rules(namespec)

            ========================== =============== ===========
            Key                        Type            Description
            ========================== =============== ===========
            'application_name'         ``str``         The Application name the process belongs to.
            'process_name'             ``str``         The Process name.
            'identifiers'              ``list(str)``   The identifiers of all |Supvisors| instances where the process
                                                       can be started.
            'start_sequence'           ``int``         The Process starting rank when starting the related application,
                                                       in [0;127].
            'stop_sequence'            ``int``         The Process stopping rank when stopping the related application,
                                                       in [0;127].
            'required'                 ``bool``        The importance of the process in the application.
            'wait_exit'                ``bool``        ``True`` if |Supvisors| has to wait for the process to exit
                                                       before triggering the next starting phase.
            'loading'                  ``int``         The Process expected loading when ``RUNNING``, in [0;100]%.
            'running_failure_strategy' ``str``         The strategy applied when a process crashes in a running
                                                       application, in [``'CONTINUE'``, ``'RESTART_PROCESS'``,
                                                       ``'STOP_APPLICATION'``, ``'RESTART_APPLICATION'``,
                                                       ``'SHUTDOWN'``, ``'RESTART'``].
            ========================== =============== ===========

        .. automethod:: get_conflicts()

            The returned structure has the same format as ``get_process_info(namespec)``.


.. _xml_rpc_supvisors:

|Supvisors| Control
-------------------

  .. autoclass:: RPCInterface
    :noindex:

        .. automethod:: change_log_level(level_param)

        .. automethod:: conciliate(strategy)

        .. automethod:: restart_sequence()

        .. automethod:: restart()

        .. automethod:: shutdown()


.. _xml_rpc_statistics:

|Supvisors| Statistics Status and Control
-----------------------------------------

  .. autoclass:: RPCInterface
    :noindex:

        .. automethod:: get_statistics_status()

            ==================== ========= ===========
            Key                  Type      Description
            ==================== ========= ===========
            'host_stats'         ``bool``  The status of Host Statistics collection in |Supvisors|.
            'process_stats'      ``bool``  The status of Process Statistics collection in |Supvisors|.
            'collecting_period'  ``float`` The minimum interval between 2 samples of the same statistics type.
            ==================== ========= ===========

        .. automethod:: enable_host_statistics(enable_host)

        .. automethod:: enable_process_statistics(enable_process)

        .. automethod:: update_collecting_period(collecting_period)


.. _xml_rpc_application:

Application Control
-------------------

  .. autoclass:: RPCInterface
    :noindex:

        .. automethod:: start_application(strategy, application_name, wait=True)

        .. automethod:: stop_application(application_name, wait=True)

        .. automethod:: restart_application(strategy, application_name, wait=True)

        .. automethod:: test_start_application(strategy, application_name)


.. _xml_rpc_process:

Process Control
---------------

  .. autoclass:: RPCInterface
    :noindex:

        .. automethod:: start_args(namespec, extra_args='', wait=True)

        .. automethod:: start_process(strategy, namespec, extra_args='', wait=True)

        .. automethod:: start_any_process(strategy, regex, extra_args='', wait=True)

        .. automethod:: stop_process(namespec, wait=True)

        .. automethod:: restart_process(strategy, namespec, extra_args='', wait=True)

        .. automethod:: test_start_process(strategy, namespec)

        .. automethod:: update_numprocs(program_name, numprocs, wait=True, lazy=False)

            .. hint::

                This XML-RPC is the implementation of the following |Supervisor| request:

                    * `#177 - Dynamic numproc change <https://github.com/Supervisor/supervisor/issues/177>`_

        .. automethod:: enable(program_name, wait=True)

            .. hint::

                This XML-RPC is a part of the implementation of the following |Supervisor| request:

                    * `#591 - New Feature: disable/enable <https://github.com/Supervisor/supervisor/issues/591>`_

        .. automethod:: disable(program_name, wait=True)

            .. hint::

                This XML-RPC is a part of the implementation of the following |Supervisor| request:

                    * `#591 - New Feature: disable/enable <https://github.com/Supervisor/supervisor/issues/591>`_

XML-RPC Clients
---------------

This section explains how to use the XML-RPC API from a :program:`Python` or :program:`JAVA` client.


:program:`Python` Client
~~~~~~~~~~~~~~~~~~~~~~~~

To perform an XML-RPC from a :program:`Python` client, |Supervisor| provides the ``getRPCInterface`` function of the
:program:`supervisor.childutils` module.

The parameter requires a dictionary with the following variables set:

    * ``SUPERVISOR_SERVER_URL``: the url of the |Supervisor| HTTP server (ex: ``http://localhost:60000``),
    * ``SUPERVISOR_USERNAME``: the user name for the HTTP authentication (may be void),
    * ``SUPERVISOR_PASSWORD``: the password for the HTTP authentication (may be void).

If the :program:`Python` client has been spawned by |Supervisor|, the environment already contains these parameters
but they are configured to communicate with the local |Supervisor| instance.

>>> import os
>>> from supervisor.childutils import getRPCInterface
>>> proxy = getRPCInterface(os.environ)
>>> proxy.supvisors.get_instance_info('cliche81')
{'identifier': 'cliche81', 'node_name': 'cliche81', 'port': 60000, 'statecode': 2, 'statename': 'RUNNING',
'sequence_counter': 885, 'remote_time': 1645285505, 'local_time': 1645285505, 'loading': 24,
'fsm_statecode': 3, 'fsm_statename': 'OPERATION', 'starting_jobs': False, 'stopping_jobs': False}

If the :program:`Python` client has to communicate with another |Supervisor| instance, the parameters must be set
accordingly.

The ``ServerProxy`` of the ``xmlrpc`` module can also be used.

>>> from xmlrpc.client import ServerProxy
>>> proxy = ServerProxy('http://cliche81:60000')
>>> proxy.supvisors.get_supvisors_state()
{'fsm_statecode': 3, 'fsm_statename': 'OPERATION', 'starting_jobs': [], 'stopping_jobs': []}


:program:`JAVA` Client
~~~~~~~~~~~~~~~~~~~~~~

There is :program:`JAVA` client *supervisord4j* referenced in the `Supervisor documentation
<http://supervisord.org/plugins.html#libraries-that-integrate-third-party-applications-with-supervisor>`_.
However, it comes with the following drawbacks, taken from the ``README.md`` of
`supervisord4j <https://github.com/satifanie/supervisord4j>`_:

    * some XML-RPC are not implemented,
    * some implemented XML-RPC are not tested,
    * of course, it doesn't include the |Supvisors| XML-RPC API.

The |Supvisors| release comes with a ``JAR`` file including a :program:`JAVA` client.
It can be downloaded from the `Supvisors releases <https://github.com/julien6387/supvisors/releases>`_.

The package ``org.supvisors.rpc`` implements all XML-RPC of all interfaces (``system``, ``supervisor``
and ``supvisors``).

This package requires the following additional dependency:

    * `Apache XML-RPC <https://ws.apache.org/xmlrpc>`_.

The binary JAR of :program:`Apache XML-RPC 3.1.3` is available in the
`Apache MAVEN repository <https://mvnrepository.com/artifact/org.apache.xmlrpc/xmlrpc/3.1.3>`_.

.. code-block:: java

    import org.supvisors.rpc.*;

    // create proxy
    SupervisorXmlRpcClient client = new SupervisorXmlRpcClient("10.0.0.1", 60000, "toto", "p@$$w0rd");

    // Supervisor XML-RPC
    SupervisorXmlRpc supervisor = new SupervisorXmlRpc(client);
    System.out.println(supervisor.getState());

    // Supvisors XML-RPC
    SupvisorsXmlRpc supvisors = new SupvisorsXmlRpc(client);
    System.out.println(supvisors.getSupvisorsState());

.. include:: common.rst
