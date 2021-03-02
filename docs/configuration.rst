.. _configuration:

Configuration
=============

Supervisor's Configuration File
-------------------------------

This section explains how **Supvisors** uses and complements the `Supervisor configuration <http://supervisord.org/configuration.html>`_.


Extension points
~~~~~~~~~~~~~~~~

**Supvisors** extends the `Supervisor's XML-RPC API <http://supervisord.org/xmlrpc.html>`_.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

**Supvisors** extends also `supervisorctl <http://supervisord.org/running.html#running-supervisorctl>`_.
This feature is not described in Supervisor documentation.

.. code-block:: ini

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


.. _supvisors_section:

``[supvisors]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The parameters of **Supvisors** are set through an additional section ``[supvisors]`` in the Supervisor configuration file.

``address_list``

    The list of node names where **Supvisors** will be running, separated by commas.

    *Default*:  local host name.

    *Required*:  Yes.

    .. attention::

        The node names are expected to be known to every related systems in the list.
        If it's not the case, check the network configuration.

    .. hint::

        If the `netifaces <https://pypi.python.org/pypi/netifaces>`_ package is installed, it is possible to use IP addresses
        in addition to node names.

        Like the node names, the IP addresses are expected to be known to every related systems in the list.
        If it's not the case, check the network configuration.


``rules_file``

    The absolute or relative path of the XML rules file. The contents of this file is described in `Supvisors' Rules File`_.

    *Default*:  None.

    *Required*:  No.

``auto_fence``

    When true, **Supvisors** won't try to reconnect to a **Supvisors** instance that is inactive.
    This functionality is detailed in :ref:`auto_fencing`.

    *Default*:  ``false``.

    *Required*:  No.

``internal_port``

    The internal port number used to publish local events to remote **Supvisors** instances.
    Events are published through a PyZMQ TCP socket.

    *Default*:  ``65001``.

    *Required*:  No.


``event_port``

    The port number used to publish all **Supvisors** events (Address, Application and Process events).
    Events are published through a PyZMQ TCP socket. The protocol of this interface is explained in :ref:`event_interface`.

    *Default*:  ``65002``.

    *Required*:  No.

``synchro_timeout``

    The time in seconds that **Supvisors** waits for all expected **Supvisors** instances to publish.
    Value in [``15`` ; ``1200``].
    This use of this option is detailed in :ref:`synchronizing`.

    *Default*:  ``15``.

    *Required*:  No.

``force_synchro_if``

    The subset of ``address_list`` that will force the end of the synchronization phase in **Supvisors**, separated by commas.
    If not set, **Supvisors** waits for all expected **Supvisors** instances to publish until ``synchro_timeout``.

    *Default*:  None.

    *Required*:  No.

``starting_strategy``

    The strategy used to start applications on nodes.
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` }.
    The use of this option is detailed in :ref:`starting_strategy`.

    *Default*:  ``CONFIG``.

    *Required*:  No.

``conciliation_strategy``

    The strategy used to solve conflicts upon detection that multiple instances of the same program are running.
    Possible values are in { ``SENICIDE``, ``INFANTICIDE``, ``USER``, ``STOP``, ``RESTART``, ``RUNNING_FAILURE`` }.
    The use of this option is detailed in :ref:`conciliation`.

    *Default*:  ``USER``.

    *Required*:  No.

``stats_periods``

    The list of periods for which the statistics will be provided in the **Supvisors** :ref:`dashboard`, separated by commas.
    Up to 3 values are allowed in [``5`` ; ``3600``] seconds, each of them MUST be a multiple of ``5``.

    *Default*:  ``10``.

    *Required*:  No.

``stats_histo``

    The depth of the statistics history. Value in [``10`` ; ``1500``].

    *Default*:  ``200``.

    *Required*:  No.

``stats_irix_mode``

    The way of presenting process CPU values.
    If true, values are displayed in 'IRIX' mode.
    If false, values are displayed in 'Solaris' mode.

    *Default*:  ``false``.

    *Required*:  No.

The logging options are strictly identical to Supervisor's. By the way, it is the same logger that is used.
These options are more detailed in `supervisord Section values <http://supervisord.org/configuration.html#supervisord-section-values>`_.

``logfile``

    The path to the **Supvisors** activity log of the supervisord process. This option can include the value ``%(here)s``,
    which expands to the directory in which the supervisord configuration file was found.
    If ``logfile`` is unset or set to ``AUTO``, **Supvisors** will use the same logger as Supervisor. It makes it easier
    to understand what happens when Supervisor and **Supvisors** output sequentially.

    *Default*:  ``AUTO``.

    *Required*:  No.

``logfile_maxbytes``

    The maximum number of bytes that may be consumed by the **Supvisors** activity log file before it is rotated
    (suffix multipliers like ``KB``, ``MB``, and ``GB`` can be used in the value).
    Set this value to ``0`` to indicate an unlimited log size. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``50MB``.

    *Required*:  No.

``logfile_backups``

    The number of backups to keep around resulting from **Supvisors** activity log file rotation.
    If set to ``0``, no backups will be kept. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``10``.

    *Required*:  No.

``loglevel``

    The logging level, dictating what is written to the **Supvisors** activity log.
    One of [``critical``, ``error``, ``warn``, ``info``, ``debug``, ``trace``,  ``blather``].
    See also: `supervisord Activity Log Levels <http://supervisord.org/logging.html#activity-log-levels>`_.
    No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``info``.

    *Required*:  No.

Configuration File Example
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

    [inet_http_server]
    port=:60000

    [supervisord]
    logfile=./log/supervisord.log
    logfile_backups=2
    loglevel=info
    pidfile=/tmp/supervisord.pid
    nodaemon=false
    umask=002

    [rpcinterface:supervisor]
    supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

    [supervisorctl]
    serverurl=http://localhost:60000

    [include]
    files = */*.ini

    # Supvisors dedicated part
    [supvisors]
    address_list=cliche01,cliche03,cliche02,cliche04
    rules_file=./etc/my_movies.xml
    auto_fence=false
    internal_port=60001
    event_port=60002
    synchro_timeout=20
    starting_strategy=LESS_LOADED
    conciliation_strategy=INFANTICIDE
    stats_periods=5,60,600
    stats_histo=100
    logfile=./log/supvisors.log
    logfile_maxbytes=50MB
    logfile_backups=10
    loglevel=info

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


.. _rules_file:

**Supvisors**' Rules File
--------------------------

This part describes the contents of the XML rules file declared in the ``rules_file`` option.

Basically, the rules file contains rules that define how applications and programs should be started and stopped,
and the quality of service expected.
It relies on the Supervisor group and program definitions.


If the `lxml <http://lxml.de>`_ package is available on the system, **Supvisors** uses it to validate
the XML rules file before it is used.

.. hint::

    It is still possible to validate the XML rules file manually.
    The XSD contents used to validate the XML can be found in the module ``supvisors.parser``.
    Once extracted to a file (here :file:`rules.xsd`), just use :command:`xmllint` to validate:

    .. code-block:: bash

        [bash] > xmllint --noout --schema rules.xsd user_rules.xml


``program`` Rules
~~~~~~~~~~~~~~~~~

The ``program`` element defines rules applicable to a program. This element must be included in an ``application`` element.
Here follows the definition of the attributes and rules applicable to a ``program`` element.

``name``

    This attribute gives the name of the program.
    It MUST correspond to a `Supervisor program name <http://supervisord.org/configuration.html#program-x-section-settings>`_.

    *Default*:  None.

    *Required*:  Yes.

``addresses``

    This element gives the list of nodes where the process can be started, separated by commas. Applicable values are:

        * a subset of the ``address_list`` defined in `[supvisors] Section Values`_,
        * ``*``: stands for all values in ``address_list``.
        * ``#``: stands for the node in ``address_list`` having the same index as the program in a homogeneous group. This will be detailed in the `Pattern Rules`_.

    *Default*:  ``*``.

    *Required*:  No.

``required``

    This element gives the importance of the program for the application.
    If ``true`` (resp. ``false``), a failure of the program is considered major (resp. minor).
    This is quite informative and is mainly used to give the operational status of the application.

    *Default*:  ``false``.

    *Required*:  No.

``start_sequence``

    This element gives the starting rank of the program when the application is starting.
    When <= ``0``, the program is not automatically started.
    When > ``0``, the program is started automatically in the given order.

    *Default*:  ``0``.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the program when the application is stopping.
    When <= ``0``, the program is stopped immediately if running.
    When > ``0``, the program is stopped in the given order.

    *Default*:  ``0``.

    *Required*:  No.

``wait_exit``

    If the value of this element is set to ``true``, **Supvisors** waits for the process to exit before starting the next sequence.
    This is particularly useful for scripts used to load a database, to mount disks, to prepare the application working directory, etc.

    *Default*:  ``false``.

    *Required*:  No.

``loading``

    This element gives the expected percent usage of *resources*. The value is a estimation and the meaning
    in terms of resources (CPU, memory, network) is in the user's hands.

    This can be used in **Supvisors** to ensure that a system is not overloaded with greedy processes.
    When multiple nodes are available, the ``loading`` value helps to distribute processes over the available nodes,
    so that the system remains safe.

    *Default*:  ``1``.

    *Required*:  No.

    .. note:: *About the choice of an user estimation*

        Although **Supvisors** may be taking measurements on each system where it is running, it has
        been chosen not to use these figures for the loading purpose. Indeed, the resources consumption
        of a process may be very variable in time and is not foreseeable.

        It is recommended to give a value based on an average usage of the resources in the worst case
        configuration and to add a margin corresponding to the standard deviation.

``running_failure_strategy``

    This element gives the strategy applied when the required process is unexpectedly stopped in a running application.
    This value supersedes the value set at application level.
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION`` }
    and are detailed in :ref:`running_failure_strategy`.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

    .. attention:: *About the Running Failure Strategy*

        This functionality is NOT compatible with the ``autostart`` parameter of the program configuration in Supervisor.
        It is undesirable that Supervisor and **Supvisors** trigger a different behaviour for the same event.
        So, unless the value of the running failure strategy is set to ``CONTINUE`` (default value), **Supvisors** forces
        ``autostart=False`` in Supervisor internal model.

        ``RESTART_PROCESS`` is almost equivalent to ``autorestart=unexpected``, except that **Supvisors** may restart
        the crashed program somewhere else, in accordance with the starting rules defined, instead of just restarting it
        on the same node.

        There is no equivalent in **Supvisors** for ``autorestart=True``. Although there are workarounds for that,
        it might be a future improvement.

``reference``

    This element gives the name of an applicable ``model``, as defined in `model Rules`_.

    *Default*:  None.

    *Required*:  No.

    .. note:: *About referencing models*

        The ``reference`` element can be combined with all the other elements described above.
        The rules got from the referenced model are loaded first and then eventually superseded by any other rule
        defined in the same program section.

        A model can reference another model. In order to prevent infinite loops and to keep a reasonable complexity,
        the maximum chain starting from the ``program`` section has been set to 3.
        As a consequence, any rule may be superseded twice at a maximum.

Here follows an example of a ``program`` definition:

.. code-block:: xml

    <program name="prg_00">
        <addresses>cliche01,cliche03,cliche02</addresses>
        <required>true</required>
        <start_sequence>1</start_sequence>
        <stop_sequence>1</stop_sequence>
        <wait_exit>false</wait_exit>
        <loading>3</loading>
        <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
    </program>


``pattern`` Rules
~~~~~~~~~~~~~~~~~

It may be quite tedious to give all this information to each program, especially if multiple programs use quite common rules.
So two mechanisms were put in place to help.

The first one is the ``pattern`` element. It can be used to configure a set of programs in a more flexible way than just
considering homogeneous programs, like Supervisor does.

Like the ``program`` element, the ``pattern`` element must be included in an ``application`` element. The same options are applicable.
The difference is in the ``name`` usage. For a pattern definition, a substring of a Supervisor program name is expected.

.. code-block:: xml

    <pattern name="prg_">
        <addresses>cliche01,cliche03,cliche02</addresses>
        <start_sequence>2</start_sequence>
        <required>true</required>
    </pattern>

.. attention:: *About the pattern names*.

    Precautions must be taken when using a ``pattern`` definition.
    In the previous example, the rules are applicable to every program names containing the ``"prg_"`` substring,
    so that it matches ``prg_00``, ``prg_dummy``, but also ``dummy_prg_2``.

    As a general rule when looking for program rules, **Supvisors** always searches for a ``program`` definition with
    the exact program name, and if not found only, **Supvisors** tries to find a corresponding ``pattern`` definition.

    It also may happen that several patterns match the same program name. In this case, **Supvisors** chooses the pattern
    with the greatest matching, or arbitrarily the first of them if such a rule does not discriminate enough.
    So considering the program ``prg_00`` and the two matching pattern names ``prg`` and ``prg_``, **Supvisors** will
    apply the rules related to ``prg_``.

.. hint:: *About the use of* ``#`` *in* ``addresses``.

    This is designed for a program that is meant to be started on every nodes of the address list.
    As an example, based on the following simplified Supervisor configuration:

    .. code-block:: ini

        [supvisors]
        address_list=cliche01,cliche02,cliche03,cliche04,cliche05

        [program:prg]
        process_name=prg_%(process_num)02d
        numprocs=5

    Without this option, it would be necessary to have one program definition for each instance.

    .. code-block:: xml

        <program name="prg_00">
            <addresses>cliche01</addresses>
        </program>

        <!-- similar definitions for prg_01, prg_02, prg_03 -->

        <program name="prg_04">
            <addresses>cliche05</addresses>
        </program>

    Now with this option, the program definition is more simple.

    .. code-block:: xml

        <pattern name="prg_">
            <addresses>#</addresses>
        </pattern>

.. attention::

    Nodes are chosen in accordance with the sequence given in ``address_list``.
    In the example above, if the two first nodes are swapped, ``prg_00`` will be addressed to ``cliche02``
    and ``prg_01`` to ``cliche01``.

.. attention::

    In the program configuration file, it is expected that the ``numprocs`` value matches the number of elements in ``address_list``.
    If the length of ``address_list`` is greater than the ``numprocs`` value, programs will be addressed to the ``numprocs`` first nodes.
    On the other side, if the length of ``address_list`` is lower than the ``numprocs`` value,
    the last programs won't be addressed to any node and it won't be possible to start them using **Supvisors**.
    Nevertheless, in this case, it will be still possible to start them with Supervisor.


``model`` Rules
~~~~~~~~~~~~~~~

The second mechanism is the ``model`` definition.
The ``program`` rules definition is extended to a generic model, that can be defined outside of the application scope,
so that the same rules definition can be applied to multiple programs, in any application.

The same options are applicable, **including** the ``reference`` option.
There is no particular expectation for the name attribute of a ``model``.

Here follows an example of model:

.. code-block:: xml

    <model name="X11_model">
        <addresses>cliche01,cliche02,cliche03</addresses>
        <start_sequence>1</start_sequence>
        <required>false</required>
        <wait_exit>false</wait_exit>
    </model>

Here follows examples of program and pattern definitions referencing a model:

.. code-block:: xml

    <program name="xclock">
        <reference>X11_model</reference>
    </program>

    <pattern name="prg">
        <reference>X11_model</reference>
        <!-- prg-like programs have the same rules as X11_model, but with required=true-->
        <required>true</required>
    </pattern>


``application`` Rules
~~~~~~~~~~~~~~~~~~~~~

Here follows the definition of the attributes and rules applicable to an ``application`` element.

``name``

    This attribute gives the name of the application.
    It MUST correspond to a `Supervisor group name <http://supervisord.org/configuration.html#group-x-section-settings>`_.

    *Default*:  None.

    *Required*:  Yes.

``start_sequence``

    This element gives the starting rank of the application in the ``DEPLOYMENT`` state, when applications are started automatically.
    When <= ``0``, the application is not started.
    When > ``0``, the application is started in the given order.

    *Default*:  ``0``.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the application when all applications are stopped just before **Supvisors** is restarted or shut down.
    When <= ``0``, **Supvisors** does nothing and let Supervisor do the job, i.e. stop everything in any order.
    When > ``0``, **Supvisors** stops the application in the given order BEFORE the restart or shutdown of Supervisor is requested.

    *Default*:  ``0``.

    *Required*:  No.

    .. attention::

        The ``stop_sequence`` is **not** taken into account:

            * when calling Supervisor's ``restart`` or ``shutdown`` XML-RPC,
            * when stopping the :command:`supervisord` daemon.

        It only works when calling **Supvisors**' ``restart`` or ``shutdown`` XML-RPC.

``starting_failure_strategy``

    This element gives the strategy applied upon a major failure in the starting phase of an application.
    Possible values are:

        * ``ABORT``: Abort the application starting.
        * ``STOP``: Stop the application.
        * ``CONTINUE``: Skip the failure and continue the application starting.

    *Default*:  ``ABORT``.

    *Required*:  No.

``running_failure_strategy``

    This element gives the strategy applied when any process of the application is unexpectedly stopped when
    the application is running. This value can be superseded by the value set at program level.
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION`` }
    and are detailed in :ref:`running_failure_strategy`.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

``program``

    This element defines the program rules that are applicable to the program whose name correspond to the name
    attribute of the ``program`` element. The program MUST be defined in the program list of
    the `Supervisor group definition <http://supervisord.org/configuration.html#group-x-section-settings>`_
    of the application considered here.
    Obviously, the definition of an application can include multiple ``program`` elements.

    *Default*:  None.

    *Required*:  No.

``pattern``

    This element defines the program rules that are applicable to all programs whose name matches the name attribute
    of the ``pattern`` element.
    Obviously, the definition of an application can include multiple ``program`` elements.

    *Default*:  None.

    *Required*:  No.


Rules File Example
~~~~~~~~~~~~~~~~~~

Here follows a complete example of rules files. It is used in **Supvisors** self tests.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>

        <!-- models -->
        <model name="disk_01">
            <addresses>cliche01</addresses>
            <expected_loading>5</expected_loading>
        </model>

        <model name="disk_02">
            <addresses>cliche02</addresses>
            <expected_loading>5</expected_loading>
        </model>

        <model name="disk_03">
            <addresses>cliche03</addresses>
            <expected_loading>5</expected_loading>
        </model>

        <model name="disk_error">
            <addresses>*</addresses>
            <expected_loading>5</expected_loading>
        </model>

        <!-- starter checking application -->
        <application name="test">
            <start_sequence>1</start_sequence>
            <stop_sequence>4</stop_sequence>

            <program name="check_start_sequence">
                <addresses>*</addresses>
                <start_sequence>1</start_sequence>
                <expected_loading>1</expected_loading>
            </program>

        </application>

        <!-- import application -->
        <application name="import_database">
            <start_sequence>2</start_sequence>
            <starting_failure_strategy>STOP</starting_failure_strategy>

            <program name="mount_disk">
                <addresses>cliche01</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>2</stop_sequence>
                <required>true</required>
                <expected_loading>0</expected_loading>
            </program>

            <program name="copy_error">
                <addresses>cliche01</addresses>
                <start_sequence>2</start_sequence>
                 <stop_sequence>1</stop_sequence>
                <required>true</required>
                <wait_exit>true</wait_exit>
                <expected_loading>25</expected_loading>
            </program>

        </application>

        <!-- movies_database application -->
        <application name="database">
            <start_sequence>3</start_sequence>
            <stop_sequence>3</stop_sequence>

            <pattern name="movie_server_">
                <addresses>#</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>1</stop_sequence>
                <expected_loading>5</expected_loading>
                <running_failure_strategy>CONTINUE</running_failure_strategy>
            </pattern>

            <pattern name="register_movies_">
                <addresses>#</addresses>
                <start_sequence>2</start_sequence>
                <wait_exit>true</wait_exit>
                <expected_loading>25</expected_loading>
            </pattern>

        </application>

        <!-- my_movies application -->
        <application name="my_movies">
            <start_sequence>4</start_sequence>
            <stop_sequence>2</stop_sequence>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>

            <program name="manager">
                <addresses>*</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>2</stop_sequence>
                <required>true</required>
                <expected_loading>5</expected_loading>
                <running_failure_strategy>RESTART_APPLICATION</running_failure_strategy>
            </program>

            <program name="web_server">
                <addresses>cliche04</addresses>
                <start_sequence>2</start_sequence>
                <required>true</required>
                <expected_loading>3</expected_loading>
            </program>

            <program name="hmi">
                <addresses>cliche02, cliche01</addresses>
                <start_sequence>3</start_sequence>
                <stop_sequence>1</stop_sequence>
                <expected_loading>10</expected_loading>
                <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
            </program>

            <pattern name="disk_01_">
                <reference>disk_01</reference>
            </pattern>

            <pattern name="disk_02_">
                <reference>disk_02</reference>
            </pattern>

            <pattern name="disk_03_">
                <reference>disk_03</reference>
            </pattern>

            <pattern name="error_disk_">
                <reference>disk_error</reference>
            </pattern>

            <program name="converter_04">
                <addresses>cliche03,cliche01,cliche02</addresses>
                <expected_loading>25</expected_loading>
            </program>

            <program name="converter_07">
                <addresses>cliche01,cliche02,cliche03</addresses>
                <expected_loading>25</expected_loading>
            </program>

            <pattern name="converter_">
                <expected_loading>25</expected_loading>
            </pattern>

         </application>

        <!-- player application -->
        <application name="player">
            <start_sequence>5</start_sequence>
            <starting_failure_strategy>ABORT</starting_failure_strategy>

            <program name="test_reader">
                <addresses>cliche01</addresses>
                <start_sequence>1</start_sequence>
                <required>true</required>
                <wait_exit>true</wait_exit>
                <expected_loading>2</expected_loading>
            </program>

            <program name="movie_player">
                <addresses>cliche01</addresses>
                <start_sequence>2</start_sequence>
                <expected_loading>13</expected_loading>
            </program>

        </application>

        <!-- web_movies application -->
        <application name="web_movies">
            <start_sequence>6</start_sequence>
            <stop_sequence>1</stop_sequence>

            <program name="web_browser">
                <addresses>*</addresses>
                <start_sequence>1</start_sequence>
                <expected_loading>4</expected_loading>
                <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
            </program>

        </application>

    </root>
