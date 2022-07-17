.. _configuration:

Configuration
=============

Supervisor's Configuration File
---------------------------------

This section explains how |Supvisors| uses and complements the
`Supervisor configuration <http://supervisord.org/configuration.html>`_.

As written in the introduction, all |Supervisor| instances **MUST** be configured with an internet socket.
``username`` and ``password`` can be used at the condition that the same values are used for all |Supervisor| instances.

.. code-block:: ini

    [inet_http_server]
    port=:60000
    ;username=lecleach
    ;password=p@$$w0rd

Apart from the ``rpcinterface`` and ``ctlplugin`` sections related to |Supvisors|, all |Supervisor| instances can have
a completely different configuration, including the list of programs.


.. _supvisors_section:

rpcinterface extension point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|Supvisors| extends the `Supervisor's XML-RPC API <http://supervisord.org/xmlrpc.html>`_.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

The parameters of |Supvisors| are set in this section of the |Supervisor| configuration file.
It is expected that some parameters are strictly identical for all |Supvisors| instances otherwise unpredictable
behavior may happen. The present section details where it is applicable.

``supvisors_list``

    The exhaustive list of |Supvisors| instances to handle, separated by commas.
    Each element should match the following format: ``<identifier>host_name:http_port:internal_port``,
    where ``identifier`` is the optional but **unique** |Supervisor| identifier (it can be set in the |Supervisor|
    configuration or in the command line when starting the ``supervisord`` program) ;
    ``host_name`` is the name of the node where the |Supvisors| instance is running ;
    ``http_port`` is the port of the internet socket used to communicate with the |Supervisor| instance (obviously
    unique per node) ;
    ``internal_port`` is the port of the socket used by the |Supvisors| instance to publish internal events (also
    unique per node).
    The value of ``supvisors_list`` defines how the |Supvisors| instances will share information between them and must
    be identical to all |Supvisors| instances or unpredictable behavior may happen.

    *Default*:  the local host name.

    *Required*:  No.

    *Identical*:  Yes.

    .. note::

        ``host_name`` can be the host name, as returned by the shell command :command:`hostname`, one of its declared
        aliases or an IP address.

    .. attention::

        The chosen host name, alias or IP address must be known to every nodes in the list on the network interface
        considered. If it's not the case, check the network configuration.

    .. hint::

        Actually, only the ``host_name`` is strictly required.

        if ``http_port`` or ``internal_port`` are not provided, the local |Supvisors| instance takes the assumption
        that the other |Supvisors| instance uses the same ``http_port`` and ``internal_port``.
        In this case, the outcome is that there cannot be 2 |Supvisors| instances on the same node.

        ``identifier`` can be seen as a nickname that may be more user-friendly than a ``host_name`` or a
        ``host_name:http_port`` when displayed in the |Supvisors| Web UI or used in the `Supvisors' Rules File`_.

    .. important:: *About the deduced names*

        Depending on the value chosen, the *deduced name* of the |Supvisors| instance may vary. As this name is expected
        to be used in the rules files to define where the processes can be started, it is important to understand how
        it is built.

        As a general rule, ``identifier`` takes precedence as a deduced name when set. Otherwise ``host_name`` is
        used when set alone, unless a ``http_port`` is explicitly defined, in which case ``host_name:http_port``
        will be used.
        A few examples:

        +------------------------------------+---------------------+
        | Configured name                    | Deduced name        |
        +====================================+=====================+
        | ``<supervisor_01>10.0.0.1:8888:``  | ``supervisor_01``   |
        +------------------------------------+---------------------+
        | ``<supervisor_01>10.0.0.1``        | ``supervisor_01``   |
        +------------------------------------+---------------------+
        | ``10.0.0.1``                       | ``10.0.0.1``        |
        +------------------------------------+---------------------+
        | ``10.0.0.1:8888:8889``             | ``10.0.0.1:8888``   |
        +------------------------------------+---------------------+

        In case of doubt, the |Supvisors| Web UI displays the deduced names in the Supervisors navigation menu.
        The names can also be found at the beginning of the |Supvisors| log traces.

        The recommendation is to uniformly use the |Supervisor| identifier.

``rules_files``

    A space-separated sequence of file globs, in the same vein as
    `supervisord include section <http://supervisord.org/configuration.html#include-section-values>`_.
    Instead of ``ini`` files, XML rules files are expected here. Their content is described in `Supvisors' Rules File`_.
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the startup sequence would
    be different depending on which |Supvisors| instance is the *Master*.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

``auto_fence``

    When true, |Supvisors| will definitely disconnect a |Supvisors| instance that is inactive.
    This functionality is detailed in :ref:`auto_fencing`.

    *Default*:  ``false``.

    *Required*:  No.

    *Identical*:  No.

``internal_port``

    The internal port number used to publish the local events to the other |Supvisors| instances.
    Events are published through a PyZMQ TCP socket.
    The value must match the ``internal_port`` value of the corresponding |Supvisors| instance in ``supvisors_list``.

    *Default*:  local |Supervisor| HTTP port + 1.

    *Required*:  No.

    *Identical*:  No.

``event_port``

    The port number used to publish all |Supvisors| events (Instance, Application and Process events).
    Events are published through a PyZMQ TCP socket. The protocol of this interface is detailed
    in :ref:`event_interface`.

    *Default*:  local |Supervisor| HTTP port + 2.

    *Required*:  No.

    *Identical*:  No.

``synchro_timeout``

    The time in seconds that |Supvisors| waits for all expected |Supvisors| instances to publish their TICK.
    Value in [``15`` ; ``1200``].
    This use of this option is detailed in :ref:`synchronizing`.

    *Default*:  ``15``.

    *Required*:  No.

    *Identical*:  No.

``inactivity_ticks``

    By default, a remote |Supvisors| instance is considered inactive when no tick has been received from it while 2
    ticks have been received fom the local |Supvisors| instance, which may be a bit strict in a busy network.
    This option allows to loosen the constraint. Value in [``2`` ; ``720``].

    *Default*:  ``2``.

    *Required*:  No.

    *Identical*:  No.

``core_identifiers``

    A subset of the names deduced from ``supvisors_list``, separated by commas. If the |Supvisors| instances of this
    subset are all in a ``RUNNING`` state, this will put an end to the synchronization phase in |Supvisors|.
    When not set, |Supvisors| waits for all expected |Supvisors| instances to publish their TICK until
    ``synchro_timeout`` seconds.
    This parameter must be identical to all |Supvisors| instances or unpredictable behavior may happen.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

``disabilities_file``

    The file path that will be used to persist the program disabilities. This option has been added in support of the
    |Supervisor| request `#591 - New Feature: disable/enable <https://github.com/Supervisor/supervisor/issues/591>`_.
    The persisted data will be serialized in a ``JSON`` string so a ``.json`` extension is recommended.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.


``starting_strategy``

    The strategy used to start applications on |Supvisors| instances.
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` , ``LESS_LOADED_NODE``,
    ``MOST_LOADED_NODE``}.
    The use of this option is detailed in :ref:`starting_strategy`.
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the startup sequence would
    be different depending on which |Supvisors| instance is the *Master*.

    *Default*:  ``CONFIG``.

    *Required*:  No.

    *Identical*:  Yes.

``conciliation_strategy``

    The strategy used to solve conflicts upon detection that multiple instances of the same program are running.
    Possible values are in { ``SENICIDE``, ``INFANTICIDE``, ``USER``, ``STOP``, ``RESTART``, ``RUNNING_FAILURE`` }.
    The use of this option is detailed in :ref:`conciliation`.
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the conciliation phase
    would behave differently depending on which |Supvisors| instance is the *Master*.

    *Default*:  ``USER``.

    *Required*:  No.

    *Identical*:  Yes.

``stats_enabled``

    By default, |Supvisors| can provide basic statistics on the node and the processes spawned by |Supervisor|
    on the |Supvisors| :ref:`dashboard`, provided that the |psutil| module is installed.
    This option can be used to disable the collection of the statistics.

    *Default*:  ``true``.

    *Required*:  No.

    *Identical*:  No.

``stats_periods``

    The list of periods for which the statistics will be provided in the |Supvisors| :ref:`dashboard`, separated by
    commas. Up to 3 values are allowed in [``5`` ; ``3600``] seconds, each of them MUST be a multiple of 5.

    *Default*:  ``10``.

    *Required*:  No.

    *Identical*:  No.

``stats_histo``

    The depth of the statistics history. Value in [``10`` ; ``1500``].

    *Default*:  ``200``.

    *Required*:  No.

    *Identical*:  No.

``stats_irix_mode``

    The way of presenting process CPU values.
    If true, values are displayed in 'IRIX' mode.
    If false, values are displayed in 'Solaris' mode.

    *Default*:  ``false``.

    *Required*:  No.

    *Identical*:  No.

The logging options are strictly identical to |Supervisor|'s. By the way, it is the same logger that is used.
These options are more detailed in
`supervisord Section values <http://supervisord.org/configuration.html#supervisord-section-values>`_.

``logfile``

    The path to the |Supvisors| activity log of the ``supervisord`` process. This option can include the value
    ``%(here)s``, which expands to the directory in which the |Supervisor| configuration file was found.
    If ``logfile`` is unset or set to ``AUTO``, |Supvisors| will use the same logger as |Supervisor|.
    It makes it easier to understand what happens when both |Supervisor| and |Supvisors| log in the same file.

    *Default*:  ``AUTO``.

    *Required*:  No.

    *Identical*:  No.

``logfile_maxbytes``

    The maximum number of bytes that may be consumed by the |Supvisors| activity log file before it is rotated
    (suffix multipliers like ``KB``, ``MB``, and ``GB`` can be used in the value).
    Set this value to ``0`` to indicate an unlimited log size. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``50MB``.

    *Required*:  No.

    *Identical*:  No.

``logfile_backups``

    The number of backups to keep around resulting from |Supvisors| activity log file rotation.
    If set to ``0``, no backups will be kept. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``10``.

    *Required*:  No.

    *Identical*:  No.

``loglevel``

    The logging level, dictating what is written to the |Supvisors| activity log.
    One of [``critical``, ``error``, ``warn``, ``info``, ``debug``, ``trace``,  ``blather``].
    See also: `supervisord Activity Log Levels <http://supervisord.org/logging.html#activity-log-levels>`_.
    No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``info``.

    *Required*:  No.

    *Identical*:  No.


ctlplugin extension point
~~~~~~~~~~~~~~~~~~~~~~~~~

|Supvisors| also extends `supervisorctl <http://supervisord.org/running.html#running-supervisorctl>`_.
This feature is not described in |Supervisor| documentation.

.. code-block:: ini

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


Configuration File Example
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

    [inet_http_server]
    port=:60000
    ;username=lecleach
    ;password=p@$$w0rd

    [supervisord]
    logfile=./log/supervisord.log
    loglevel=info
    pidfile=/tmp/supervisord.pid

    [rpcinterface:supervisor]
    supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

    [supervisorctl]
    serverurl=http://localhost:60000

    [include]
    files = common/*/*.ini %(host_node_name)s/*.ini  %(host_node_name)s/*/*.ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = cliche81,<cliche82>192.168.1.49,cliche83:60000:60001,cliche84
    rules_files = ./etc/my_movies*.xml
    auto_fence = false
    internal_port = 60001
    event_port = 60002
    synchro_timeout = 20
    inactivity_ticks = 3
    core_identifiers = cliche81,cliche82
    disabilities_file = /tmp/disabilities.json
    starting_strategy = CONFIG
    conciliation_strategy = USER
    stats_enabled = true
    stats_periods = 5,60,600
    stats_histo = 100
    stats_irix_mode = false
    logfile = ./log/supvisors.log
    logfile_maxbytes = 50MB
    logfile_backups = 10
    loglevel = debug

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


.. _rules_file:

|Supvisors|' Rules File
-----------------------

This part describes the contents of the XML rules files declared in the ``rules_files`` option.

Basically, a rules file contains rules that define how applications and programs should be started and stopped,
and the quality of service expected. It relies on the |Supervisor| group and program definitions.

.. important:: *About the declaration of Supervisor groups/processes in a rules file*

    It is important to notice that all applications declared in this file will be considered as *Managed*
    by |Supvisors|. The main consequence is that |Supvisors| will try to ensure that one single instance of the program
    is running over all the |Supvisors| instances considered. If two instances of the same program are running in two
    different |Supvisors| instances, |Supvisors| will consider this as a conflict.
    Only the *Managed* applications have an entry in the navigation menu of the |Supvisors| Web UI.

    The groups declared in |Supervisor| configuration files and not declared in a rules file will thus be considered
    as *Unmanaged* by |Supvisors|. So they have no entry in the navigation menu of the |Supvisors| web page.
    There can be as many running instances of the same program as |Supervisor| allows over the available |Supvisors|
    instances.

If the `lxml <http://lxml.de>`_ package is available on the system, |Supvisors| uses it to validate the XML rules files
before they are used.

.. hint::

    It is still possible to validate the XML rules files manually. The XSD file :file:`rules.xsd` used to validate the
    XML can be found in the |Supvisors| package. Just use :command:`xmllint` to validate:

    .. code-block:: bash

        [bash] > xmllint --noout --schema rules.xsd user_rules.xml


``<application>`` rules
~~~~~~~~~~~~~~~~~~~~~~~

Here follows the definition of the attributes and rules applicable to an ``application`` element.

``name``

    This attribute gives the name of the application. The name MUST match a
    `Supervisor group name <http://supervisord.org/configuration.html#group-x-section-settings>`_.

    *Default*:  None.

    *Required*:  Yes, unless a ``pattern`` attribute is provided.

``pattern``

    A regex matching one or more |Supervisor| group names is expected in this attribute.
    Refer to `Using patterns`_ for more details.

    *Default*:  None.

    *Required*:  Yes, unless a ``name`` attribute is provided.

.. note::

    The options below can be declared in any order in the ``application`` section.

``distribution``

    In the introduction, it is written that the aim of |Supvisors| is to manage distributed applications.
    However, it may happen that some applications are not designed to be distributed (for example due to inter-process
    communication design) and thus distributing the application processes over multiple nodes would just make
    the application non operational.
    If set to ``ALL_INSTANCES``, |Supvisors| will distribute the application processes over the applicable |Supvisors|
    instances.
    If set to ``SINGLE_INSTANCE``, |Supvisors| will start all the application processes in the same |Supvisors|
    instance.
    If set to ``SINGLE_NODE``, |Supvisors| will distribute all the application processes over a set of |Supvisors|
    instances running on the same node.

    *Default*:  ``ALL_INSTANCES``.

    *Required*:  No.

.. note::

    When a single |Supvisors| instance is running on each node, ``SINGLE_INSTANCE`` and ``SINGLE_NODE`` are strictly
    equivalent.

``identifiers``

    This element is only used when ``distribution`` is set to ``SINGLE_INSTANCE`` or ``SINGLE_NODE`` and gives the list
    of |Supvisors| instances where the application programs can be started. The names are to be taken from the names
    deduced from the ``supvisors_list`` parameter defined in `rpcinterface extension point`_ or from the declared
    `Instance aliases`_, and separated by commas.
    Special values can be used.

    The wildcard ``*`` stands for all names deduced from ``supvisors_list``.
    Any name list including a ``*`` is strictly equivalent to ``*`` alone.

    The hashtag ``#`` can be used with a ``pattern`` definition and eventually complemented by a list of deduced names.
    The aim is to assign the Nth deduced name of ``supvisors_list`` or the Nth name of the subsequent list
    (made of names deduced from ``supvisors_list``) to the Nth instance of the application, **assuming that 'N' is
    provided at the end of the application name, preceded by a dash or an underscore**.
    Yeah, a bit tricky to explain... Examples will be given in `Using patterns and hashtags`_.

    *Default*:  ``*``.

    *Required*:  No.

.. attention::

    When the distribution of the application is restricted (``distribution`` not set to ``ALL_INSTANCES``), the rule
    ``identifiers`` of the application programs is not considered.

``start_sequence``

    This element gives the starting rank of the application in the ``DEPLOYMENT`` state,
    when applications are started automatically.
    When <= ``0``, the application is not started.
    When > ``0``, the application is started in the given order.

    *Default*:  ``0``.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the application when all applications are stopped just before |Supvisors|
    is restarted or shut down. This value must be positive. If not set, it is defaulted to the ``start_sequence`` value.
    |Supvisors| stops the applications sequentially from the greatest rank to the lowest.

    *Default*:  ``start_sequence`` value.

    *Required*:  No.

    .. attention::

        The ``stop_sequence`` is **not** taken into account:

            * when calling |Supervisor|'s ``restart`` or ``shutdown`` XML-RPC,
            * when stopping the :command:`supervisord` daemon.

        It only works when calling |Supvisors|' ``restart`` or ``shutdown`` XML-RPC.

``starting_strategy``

    The strategy used to start applications on |Supvisors| instances.
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` }.
    The use of this option is detailed in :ref:`starting_strategy`.

    *Default*:  the value set in the :ref:`supvisors_section` of the |Supervisor| configuration file.

    *Required*:  No.

``starting_failure_strategy``

    This element gives the strategy applied upon a major failure, i.e. happening on a required process,
    in the starting phase of an application.
    The possible values are { ``ABORT``, ``STOP``, ``CONTINUE`` } and are detailed in :ref:`starting_failure_strategy`.

    *Default*:  ``ABORT``.

    *Required*:  No.

``running_failure_strategy``

    This element gives the strategy applied when the application loses running processes due to a |Supvisors| instance
    that becomes silent (crash, power down, network failure, etc).
    This value can be superseded by the value set at program level.
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION``,
    ``SHUTDOWN``, ``RESTART`` }
    and are detailed in :ref:`running_failure_strategy`.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

``programs``

    This element is the grouping section of all ``program`` rules that are applicable to the application.
    Obviously, the ``programs`` element of an application can include multiple ``program`` elements.

    *Default*:  None.

    *Required*:  No.

``program``

    In a ``programs`` section, this element defines the rules that are applicable to the program whose name matches
    the ``name`` or ``pattern`` attribute of the element. The ``name`` must match exactly a program name in the program
    list of the `Supervisor group definition <http://supervisord.org/configuration.html#group-x-section-settings>`_
    for the application considered here.

    *Default*:  None.

    *Required*:  No.


``<program>`` rules
~~~~~~~~~~~~~~~~~~~

The ``program`` element defines the rules applicable to at least one program. This element should be included in an
``programs`` element. *DEPRECATED* It can be also directly included in an ``application`` element.
Here follows the definition of the attributes and rules applicable to this element.

.. note::

    The options below can be declared in any order in the ``program`` section.

``name``

    This attribute MUST match exactly the name of a program as defined in
    `Supervisor program settings <http://supervisord.org/configuration.html#program-x-section-settings>`_.

    *Default*:  None.

    *Required*:  Yes, unless an attribute ``pattern`` is provided.

``pattern``

    A regex matching one or more |Supervisor| program names is expected in this attribute.
    Refer to the `Using patterns`_ for more details.

    *Default*:  None.

    *Required*:  Yes, unless an attribute ``name`` is provided.

``identifiers``

    This element gives the list of |Supvisors| instances where the program can be started.
    The names are to be taken from the names deduced from the ``supvisors_list`` parameter defined in the
    `rpcinterface extension point`_ or from the declared `Instance aliases`_, and separated by commas.
    Special values can be applied.

    The wildcard ``*`` stands for all names deduced from ``supvisors_list``.
    Any name list including a ``*`` is strictly equivalent to ``*`` alone.

    The hashtag ``#`` can be used with a ``pattern`` definition and eventually complemented by a list of deduced names.
    The aim is to assign the Nth deduced name of ``supvisors_list`` or the Nth name of the subsequent list (made of
    names deduced from ``supvisors_list``) to the Nth instance of the program in a homogeneous process group.
    Examples will be given in `Using patterns and hashtags`_.

    *Default*:  ``*``.

    *Required*:  No.

``required``

    This element gives the importance of the program for the application.
    If ``true`` (resp. ``false``), a failure of the program is considered major (resp. minor).
    This is quite informative and is mainly used to give the operational status of the application in the Web UI.

    *Default*:  ``false``.

    *Required*:  No.

``start_sequence``

    This element gives the starting rank of the program when the application is starting.
    When <= ``0``, the program is not started automatically.
    When > ``0``, the program is started automatically in the given order.

    *Default*:  ``0``.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the program when the application is stopping.
    This value must be positive. If not set, it is defaulted to the ``start_sequence`` value.
    |Supvisors| stops the processes sequentially from the greatest rank to the lowest.

    *Default*:  ``start_sequence`` value.

    *Required*:  No.

``wait_exit``

    If the value of this element is set to ``true``, |Supvisors| waits for the process to exit before starting
    the next sequence. This may be particularly useful for scripts used to load a database, to mount disks, to prepare
    the application working directory, etc.

    *Default*:  ``false``.

    *Required*:  No.

``expected_loading``

    This element gives the expected percent usage of *resources*. The value is a estimation and the meaning
    in terms of resources (CPU, memory, network) is in the user's hands.

    When multiple |Supvisors| instances are available, |Supvisors| uses the ``expected_loading`` value to distribute
    the processes over the available |Supvisors| instances, so that the system remains safe.

    *Default*:  ``0``.

    *Required*:  No.

    .. note:: *About the choice of an user estimation*

        Although |Supvisors| may be taking measurements on each node where it is running, it has been chosen not to use
        these figures for the loading purpose. Indeed, the resources consumption of a process may be very variable
        in time and is not foreseeable.

        It is recommended to give a value based on an average usage of the resources in the worst case
        configuration and to add a margin corresponding to the standard deviation.

``starting_failure_strategy``

    This element gives the strategy applied upon a major failure, i.e. happening on a required process,
    in the starting phase of an application. This value supersedes the value eventually set at application level.
    The possible values are { ``ABORT``, ``STOP``, ``CONTINUE`` } and are detailed in :ref:`starting_failure_strategy`.

    *Default*:  ``ABORT``.

    *Required*:  No.

``running_failure_strategy``

    This element gives the strategy applied when the process is running in a |Supvisors| instance that becomes silent
    (crash, power down, network failure, etc). This value supersedes the value eventually set at application level.
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION``,
    ``SHUTDOWN``, ``RESTART`` }
    and their impact is detailed in :ref:`running_failure_strategy`.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

``reference``

    This element gives the name of an applicable ``model``, as defined in `<model> rules`_.

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
        <identifiers>cliche01,cliche03,cliche02</identifiers>
        <required>true</required>
        <start_sequence>1</start_sequence>
        <stop_sequence>1</stop_sequence>
        <wait_exit>false</wait_exit>
        <expected_loading>3</expected_loading>
        <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
    </program>


Using patterns
~~~~~~~~~~~~~~

It may be quite tedious to give all this information to every programs, especially if multiple programs use a common
set of rules. So two mechanisms are put in place to help.

The first one is the ``pattern`` attribute that may be used instead of the ``name`` attribute in a ``program`` element.
It can be used to configure a set of programs in a more flexible way than just considering homogeneous programs,
like |Supervisor| does.

The same ``program`` options are applicable, whatever a ``name`` attribute or a ``pattern`` attribute is used.
For a ``pattern`` attribute, a regex (or a simple substring) matching one |Supervisor| program name or more is expected.

.. code-block:: xml

    <program pattern="prg_">
        <identifiers>cliche01,cliche03,cliche02</identifiers>
        <start_sequence>2</start_sequence>
        <required>true</required>
    </program>

.. attention:: *About the pattern names*.

    Precautions must be taken when using a ``pattern`` definition.
    In the previous example, the rules are applicable to every program names containing the ``"prg_"`` substring,
    so that it matches :program:`prg_00`, :program:`prg_dummy`, but also :program:`dummy_prg_2`.

    As a general rule when looking for program rules, |Supvisors| always searches for a ``program`` definition having
    the exact program name set in the ``name`` attribute, and only if not found, |Supvisors| tries to find a
    corresponding ``program`` definition with a matching ``pattern``.

    It also may happen that multiple patterns match the same program name. In this case, |Supvisors| chooses the
    pattern with the greatest matching, or arbitrarily the first of them if such a rule does not discriminate enough.
    So considering the program :program:`prg_00` and the two matching patterns ``prg`` and ``prg_``, |Supvisors| will
    apply the rules related to ``prg_``.

The ``pattern`` attribute can be applied to ``application`` elements too. The same logic as per ``program`` elements
applies. This is particularly useful in a context where many users over multiple nodes need to have
their own application.

.. note::

    |Supervisor| does not provide support for *homogeneous* groups. So in order to have N running instances of the same
    application, the only possible solution is to define N times the |Supervisor| group using a variation in the group
    name (e.g. an index suffix). It is however possible to include the same |Supervisor| program definitions into
    different groups.

    Unfortunately, using *homogeneous* program groups with ``numprocs`` set to N cannot help in the present case because
    |Supervisor| considers the program name in the group and not the ``process_name``.

.. hint::

    As it may be a bit clumsy to define the N definition sets, a script :command:`supvisors_breed` is provided in
    |Supvisors| package to help the user to duplicate an application from a template.
    Use examples can be found in the |Supvisors| use cases :ref:`scenario_2` and :ref:`scenario_3`.


.. _patterns_hashtags:

Using patterns and hashtags
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using a hashtag ``#`` in the program ``identifiers`` is designed for a program that is meant to be started on every
|Supvisors| instances available, or on a subset of them.

As an example, based on the following simplified |Supervisor| configuration:

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = cliche01,cliche02,cliche03,cliche04,cliche05

    [program:prg]
    process_name=prg_%(process_num)02d
    numprocs=5
    numprocs_start=1

Without this option, it is necessary to define rules for all instances of the program.

.. code-block:: xml

    <program name="prg_01">
        <identifiers>cliche01</identifiers>
    </program>

    <!-- similar definitions for prg_02, prg_03, prg_04 -->

    <program name="prg_05">
        <identifiers>cliche05</identifiers>
    </program>

Now with this option, the rule becomes more simple.

.. code-block:: xml

    <program pattern="prg_\d+">
        <identifiers>#</identifiers>
    </program>

It is also possible to give a subset of deduced names.

.. code-block:: xml

    <program pattern="prg_\d+">
        <identifiers>#,cliche04,cliche02</identifiers>
    </program>

.. note::

    |Supvisors| instances are chosen in accordance with the sequence given in ``supvisors_list`` or in the subsequent
    list. In the second example above, :program:`prg_01` will be assigned to ``cliche04`` and :program:`prg_02` to
    ``cliche02``.

    |Supvisors| does take into account the start index defined in ``numprocs_start``.

.. important::

    In the initial |Supvisors| design, it was expected that the ``numprocs`` value set in the program configuration file
    would match the number of elements in ``supvisors_list``.

    However, if the number of elements in ``supvisors_list`` is greater than the ``numprocs`` value, programs will
    be assigned to the ``numprocs`` first |Supvisors| instances.

    On the other side, if the number of elements in ``supvisors_list`` is lower than the ``numprocs`` value,
    the assignment will roll over the elements in ``supvisors_list`` in a *modulo* fashion. As a consequence,
    there will be multiple programs assigned to a single |Supvisors| instance.

.. attention::

    As pointed out just before, |Supvisors| takes the information from the program configuration. So this function
    will definitely NOT work if the program is unknown to the local |Supervisor|, which is a relevant use case.
    As written before, the |Supervisor| configuration can be different for all |Supvisors| instances, including
    the definition of groups and programs.

.. important:: *Convention for application names when using patterns and hashtags*

    When the hashtag is used for the application ``identifiers``, |Supvisors| cannot rely on the |Supervisor|
    configuration to map the application instances to the |Supvisors| instances.

    By convention, the application name MUST end with ``-N`` or ``_N``. The Nth application will be mapped to the Nth
    deduced name of the list, i.e. the name at index ``N-1`` in the list.

    ``N`` must be strictly positive. Zero-padding is allowed, as long as ``N`` can be converted into an integer.


``<model>`` rules
~~~~~~~~~~~~~~~~~

The second mechanism is the ``model`` definition.
The ``program`` rules definition is extended to a generic model, that can be defined outside of the application scope,
so that the same rules definition can be applied to multiple programs, in any application.

The same options are applicable, **including** the ``reference`` option (recursion is yet limited to a depth of 2).
There is no particular expectation for the ``name`` attribute of a ``model``.

Here follows an example of model:

.. code-block:: xml

    <model name="X11_model">
        <identifiers>cliche01,cliche02,cliche03</identifiers>
        <start_sequence>1</start_sequence>
        <required>false</required>
        <wait_exit>false</wait_exit>
    </model>

Here follows examples of ``program`` definitions referencing a model:

.. code-block:: xml

    <program name="xclock">
        <reference>X11_model</reference>
    </program>

    <program pattern="prg">
        <reference>X11_model</reference>
        <!-- prg-like programs have the same rules as X11_model, but with required=true-->
        <required>true</required>
    </program>


Instance aliases
~~~~~~~~~~~~~~~~

When dealing with long lists of |Supvisors| instances, the content of application or program ``identifiers`` options
may impair the readability of the rules file. It is possible to declare instance aliases and to use the alias names
in place of the deduced names in the ``identifiers`` option.

Here follows a few usage examples:

.. code-block:: xml

    <alias name="consoles">console01,console02,console03</alias>
    <alias name="servers">server01,server02</alias>

    <!-- working alias reference -->
    <alias name="all_ok">servers,consoles</alias>

    <model name="hci">
        <identifiers>consoles</identifiers>
    </model>

    <model name="service">
        <identifiers>servers,consoles</identifiers>
    </model>

.. hint:: *About aliases referencing other aliases*

    Based on the previous example, an alias referencing other aliases will only work if it is placed *before*
    the aliases referenced.

    At some point, the resulting names are checked against the names deduced from the ``supvisors_list`` parameter
    of the `rpcinterface extension point`_ so any unknown name or remaining alias will simply be discarded.

.. code-block:: xml

    <!-- Correct alias reference -->
    <alias name="all_ok">servers,consoles</alias>

    <alias name="consoles">console01,console02,console03</alias>
    <alias name="servers">server01,server02</alias>

    <!-- Wrong alias reference -->
    <alias name="all_ko">servers,consoles</alias>


Rules File Example
~~~~~~~~~~~~~~~~~~

Here follows a complete example of a rules file. It is used in |Supvisors| self tests.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>

        <!-- aliases -->
        <alias name="distribute_sublist">#,cliche82,cliche83:60000,cliche84</alias>
        <alias name="consoles">cliche82,cliche81</alias>

        <!-- models -->
        <model name="disk_01">
            <identifiers>cliche81</identifiers>
            <expected_loading>5</expected_loading>
        </model>

        <model name="disk_02">
            <reference>disk_01</reference>
            <identifiers>cliche82</identifiers>
        </model>

        <model name="disk_03">
            <reference>disk_01</reference>
            <identifiers>cliche83:60000</identifiers>
        </model>

        <model name="converter">
            <identifiers>*</identifiers>
            <expected_loading>25</expected_loading>
        </model>

        <!-- import application -->
        <application name="import_database">
            <start_sequence>2</start_sequence>
            <starting_failure_strategy>STOP</starting_failure_strategy>

            <programs>
                <program pattern="mount_disk_">
                    <identifiers>distribute_sublist</identifiers>
                    <start_sequence>1</start_sequence>
                    <required>true</required>
                    <expected_loading>0</expected_loading>
                </program>

                <program name="copy_error">
                    <identifiers>cliche81</identifiers>
                    <start_sequence>2</start_sequence>
                    <required>true</required>
                    <wait_exit>true</wait_exit>
                    <expected_loading>25</expected_loading>
                </program>
            </programs>

        </application>

        <!-- movies_database application -->
        <application name="database">
            <start_sequence>3</start_sequence>

            <programs>
                <program pattern="movie_server_">
                    <identifiers>#</identifiers>
                    <start_sequence>1</start_sequence>
                    <expected_loading>5</expected_loading>
                    <running_failure_strategy>CONTINUE</running_failure_strategy>
                </program>

                <program pattern="register_movies_">
                    <identifiers>#,cliche81,cliche83:60000</identifiers>
                    <start_sequence>2</start_sequence>
                    <wait_exit>true</wait_exit>
                    <expected_loading>25</expected_loading>
                </program>
            </programs>

        </application>

        <!-- my_movies application -->
        <application name="my_movies">
            <start_sequence>4</start_sequence>
            <starting_strategy>CONFIG</starting_strategy>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>

            <programs>
                <program name="manager">
                    <identifiers>*</identifiers>
                    <start_sequence>1</start_sequence>
                    <stop_sequence>3</stop_sequence>
                    <required>true</required>
                    <expected_loading>5</expected_loading>
                    <running_failure_strategy>RESTART_APPLICATION</running_failure_strategy>
                </program>

                <program name="web_server">
                    <identifiers>cliche84</identifiers>
                    <start_sequence>2</start_sequence>
                    <required>true</required>
                    <expected_loading>3</expected_loading>
                </program>

                <program name="hmi">
                    <identifiers>consoles</identifiers>
                    <start_sequence>3</start_sequence>
                    <stop_sequence>1</stop_sequence>
                    <expected_loading>10</expected_loading>
                    <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
                </program>

                <program pattern="disk_01_">
                    <reference>disk_01</reference>
                </program>

                <program pattern="disk_02_">
                    <reference>disk_02</reference>
                </program>

                <program pattern="disk_03_">
                    <reference>disk_03</reference>
                </program>

                <program pattern="error_disk_">
                    <reference>disk_01</reference>
                    <identifiers>*</identifiers>
                </program>

                <program name="converter_04">
                    <reference>converter</reference>
                    <identifiers>cliche83:60000,cliche81,cliche82</identifiers>
                </program>

                <program name="converter_07">
                    <reference>converter</reference>
                    <identifiers>cliche81,cliche83:60000,cliche82</identifiers>
                </program>

                <program pattern="converter_">
                    <reference>converter</reference>
                </program>
            <programs>

         </application>

        <!-- player application -->
        <application name="player">
            <distribution>SINGLE_INSTANCE</distribution>
            <identifiers>cliche81,cliche83:60000</identifiers>
            <start_sequence>5</start_sequence>
            <starting_strategy>MOST_LOADED</starting_strategy>
            <starting_failure_strategy>ABORT</starting_failure_strategy>

            <programs>
                <program name="test_reader">
                    <start_sequence>1</start_sequence>
                    <required>true</required>
                    <wait_exit>true</wait_exit>
                    <expected_loading>2</expected_loading>
                </program>

                <program name="movie_player">
                    <start_sequence>2</start_sequence>
                    <expected_loading>13</expected_loading>
                </program>
            </programs>

        </application>

        <!-- web_movies application -->
        <application pattern="web_">
            <start_sequence>6</start_sequence>
            <stop_sequence>2</stop_sequence>
            <starting_strategy>LESS_LOADED</starting_strategy>

            <programs>
                <program name="web_browser">
                    <identifiers>*</identifiers>
                    <start_sequence>1</start_sequence>
                    <expected_loading>4</expected_loading>
                    <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
                </program>
            </programs>

        </application>

        <!-- disk_reader_81 application -->
        <application name="disk_reader_81">
            <start_sequence>1</start_sequence>
        </application>

    </root>

.. include:: common.rst
