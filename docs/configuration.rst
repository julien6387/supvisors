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

    The list of expected |Supvisors| instances to handle, separated by commas. |br|
    The elements of ``supvisors_list`` define how the |Supvisors| instances will share information between them
    and MUST be identical to all |Supvisors| instances or unpredictable behavior may happen.

    The exhaustive form of an element matches ``<nick_identifier>host_name:http_port``, where:

        * ``nick_identifier`` is the optional but **unique** |Supervisor| identifier (it can be set in the |Supervisor|
          configuration or in the command line when starting the ``supervisord`` program) ;
        * ``host_name`` is the name of the node where the |Supvisors| instance is running ;
        * ``http_port`` is the port of the internet socket used to communicate with the |Supervisor| instance
          (obviously unique per node).

    *Default*:  the host name, as given by the ``socket.gethostname()`` function.

    *Required*:  No.

    *Identical*:  Yes.

    .. note::

        ``host_name`` can be a host name, a fully qualified domain name, a node alias or an IP address.

    .. important::

        The chosen name or IP address must be known to every node declared in the ``supvisors_list``
        on the network interface considered, or |Supvisors| internal communication will fail. |br|
        Check the network configuration.

    .. important::

        The local |Supvisors| instance must identify itself in one element of the list. |br|
        To that end, |Supvisors| tries to match these items with the elements returned by the ``socket.gethostbyaddr``
        function applied to the main IP address of every network interface. |br|
        Check the network configuration.

     .. note::

        In user-related features (options, rules, XML-RPC) where a |Supvisors| identifier is requested,
        ``nick_identifier`` and ``host_name:http_port`` can both be used indifferently.

    .. hint::

        If the |Supvisors| is configured with at most one |Supvisors| instance per host, the ``host_name`` alone is a
        fully acceptable declaration.

    .. hint::

        ``nick_identifier`` can be seen as a nickname that may be more user-friendly than a ``host_name`` or a
        ``host_name:http_port`` when displayed in the |Supvisors| Web UI or used in the `Supvisors' Rules File`_.

    .. attention::

        if ``http_port`` is not provided, the local |Supvisors| instance takes the assumption that the other |Supvisors|
        instance uses the same ``http_port``. The ``http_port`` *MUST* be set if there multiple |Supvisors| instances
        running on the same node.

    .. important::

        As a general rule, |Supvisors| uses the form ``host_name:http_port`` to exchange information between the
        |Supvisors| instances. |br|
        Unless a ``nick_identifier`` is provided, this form will also be used on all user interfaces (configuration
        files, Web UI, XML-RPC and logs).

``software_name``

    An optional string that will be displayed at the top of the |Supvisors| Web UI. It is intended to correspond to
    the name of the user software.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.

``software_icon``

    An optional image that will be displayed at the top of the |Supvisors| Web UI. It is intended to correspond to
    the name of the user software.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.

    .. hint::

        ``software_icon`` are ``software_name`` can both be set and will be displayed in that order if required.

``multicast_group``

    The IP address and port number of the Multicast Group where the |Supvisors| instances will share their identity
    between them, separated by a colon (example: ``239.0.0.1:1234``). |br|
    This is an alternative to the ``supvisors_list`` option, that allows |Supvisors| to work in a discovery mode.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

    .. hint::

        Although it is an alternative, this option can yet be combined with ``supvisors_list``. |br|
        In this case, the |Supvisors| instances declared in the ``supvisors_list`` option will form an initial group
        that may grow when other unknown |Supvisors| instances declare themselves.

``multicast_interface``

    The network interface where the |Supvisors| multicast group will be bound.
    If not set, ``INADDR_ANY`` will be applied so as to bind on all network interfaces.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

``multicast_ttl``

    The time-to-live of a message sent on the |Supvisors| multicast interface.

    *Default*:  ``1``.

    *Required*:  No.

    *Identical*:  Yes.

``stereotypes``

    A list of names, separated by commas, that can be used to reference a kind of |Supvisors| instance in the rules
    files. The local |Supvisors| instance will be tagged using these names and will share this information with the
    other |Supvisors| instances. |br|
    Although it has been designed to support the discovery mode, it is made available to the standard mode.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.

``rules_files``

    A space-separated sequence of file globs, in the same vein as
    `supervisord include section <http://supervisord.org/configuration.html#include-section-values>`_.
    Instead of ``ini`` files, XML rules files are expected here. Their content is described in
    `Supvisors' Rules File`_. |br|
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the startup sequence would
    be different depending on which |Supvisors| instance is given the *Master* role.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

``auto_fence``

    When true, |Supvisors| will definitely disconnect a |Supvisors| instance that is inactive. |br|
    This functionality is detailed in :ref:`auto_fencing`.

    *Default*:  ``false``.

    *Required*:  No.

    *Identical*:  No.


``event_link``

    The communication protocol type used to publish all |Supvisors| events (Instance, Application
    and Process events). |br|
    Value in [``NONE`` ; ``ZMQ`` ; ``WS``]. Other protocols may be considered in the future. |br|
    If set to ``NONE``, the interface is not available. |br|
    If set to ``ZMQ``, events are published through a |ZeroMQ| TCP socket. |br|
    If set to ``WS``, events are published through |Websockets| (requires a :command:`Python` version 3.7
    or later). |br|
    The protocol of this interface is detailed in :ref:`event_interface`.

    *Default*:  NONE.

    *Required*:  No.

    *Identical*:  No.

``event_port``

    The port number used to publish all |Supvisors| events (Instance, Application, Process and Statistics events). |br|
    The protocol of this interface is detailed in :ref:`event_interface`.

    *Default*:  local |Supervisor| HTTP port + 1.

    *Required*:  No.

    *Identical*:  No.

``synchro_options``

    The conditions applied by |Supvisors| to exit the ``INITIALIZATION`` state. |br|
    Multiple values in [``LIST`` ; ``TIMEOUT`` ; ``CORE`` ; ``USER``], separated by commas. |br|
    If ``STRICT`` is selected, |Supvisors| exits the ``INITIALIZATION`` state when all the |Supvisors| instances
    declared in the ``supvisors_list`` option are in the ``RUNNING`` state. |br|
    If ``LIST`` is selected, |Supvisors| exits the ``INITIALIZATION`` state when all known |Supvisors| instances
    (including those declared in the ``supvisors_list`` option **AND** those discovered) are in the ``RUNNING`` state.
    If ``TIMEOUT`` is selected, |Supvisors| exits the ``INITIALIZATION`` state after the duration defined in the
    ``synchro_timeout`` option. |br|
    If ``CORE`` is selected, |Supvisors| exits the ``INITIALIZATION`` state when all the |Supvisors| instances
    identified in the ``core_identifiers`` option are in a ``RUNNING`` state. |br|
    If ``USER`` is selected, |Supvisors| exits the ``INITIALIZATION`` state as soon as the *Master* instance is set,
    which can be triggered upon user request (using the |Supvisors| Web UI, the ``end_sync`` XML-RPC or the ``end_sync``
    command of ``supervisorctl``). |br|
    The use of this option is more detailed in :ref:`synchronizing`.

    *Default*:  ``STRICT,TIMEOUT,CORE``.

    *Required*:  No.

    *Identical*:  No.

``synchro_timeout``

    The time in seconds that |Supvisors| waits for all expected |Supvisors| instances to publish their TICK.
    Value in [``15`` ; ``1200``]. |br|
    This option is taken into account only if ``TIMEOUT`` is selected in the ``synchro_options``. |br|
    The use of this option is more detailed in :ref:`synchronizing`.

    *Default*:  ``15``.

    *Required*:  No.

    *Identical*:  No.

``inactivity_ticks``

    By default, a remote |Supvisors| instance is considered inactive when no tick has been received from it while 2
    ticks have been received fom the local |Supvisors| instance, which may be a bit strict in a busy network. |br|
    This delay is also used when starting / stopping a process, considering that process events are expected in due
    time. |br|
    This option allows to loosen the constraint. Value in [``2`` ; ``720``].

    *Default*:  ``2``.

    *Required*:  No.

    *Identical*:  No.

    .. note::

        This option originates from a previous |Supvisors| design where the event publication mechanism did not allow
        to assess the consideration of the request by the remote |Supvisors| instance. In the current design, an
        inactive |Supvisors| instance is detected before a timeout is triggered on missing expected events.
        The option has thus less interest but it is kept anyway for robustness value.

``core_identifiers``

    A list of names, separated by commas. These names can taken from the names deduced from the ``supvisors_list``
    option and / or from the union of all ``stereotypes`` shared within |Supvisors|. |br|
    If the |Supvisors| instances of this subset are all in a ``RUNNING`` state and the ``CORE`` value is set
    in the ``synchro_options`` option, this will put an end to the synchronization phase in |Supvisors|. |br|
    Independently from the ``CORE`` option being used, |Supvisors| will preferably take a member of this list when
    selecting a *Master* instance. |br|
    This parameter must be identical to all |Supvisors| instances or unpredictable behavior may happen.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

``supvisors_failure_strategy``

    The strategy used when the conditions implied by the ``synchro_options`` are not met anymore.
    As an example, is the system still operational when a |Supvisors| *Core* instance is missing? |br|
    Possible values are in { ``CONTINUE``, ``RESYNC``, ``SHUTDOWN``}. |br|
    If ``CONTINUE`` is selected, |Supvisors| will deal with the missing |Supvisors| instance and continue
    in a degraded mode. |br|
    If ``RESYNC`` is selected, |Supvisors| will transition to the ``SYNCHRONIZATION`` state and wait for the selected
    conditions to be met again. |br|
    If ``SHUTDOWN`` is selected, |Supvisors| will shut down.
    It is highly recommended that this parameter is identical to all |Supvisors| instances or |Supvisors| may become
    inconsistent.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

    *Identical*:  Yes.

``starting_strategy``

    The strategy used to start applications on |Supvisors| instances. |br|
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` , ``LESS_LOADED_NODE``,
    ``MOST_LOADED_NODE``}. |br|
    The use of this option is detailed in :ref:`starting_strategy`. |br|
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the startup sequence would
    be different depending on which |Supvisors| instance is the *Master*.

    *Default*:  ``CONFIG``.

    *Required*:  No.

    *Identical*:  Yes.

``conciliation_strategy``

    The strategy used to solve conflicts upon detection that multiple instances of the same program are running. |br|
    Possible values are in { ``SENICIDE``, ``INFANTICIDE``, ``USER``, ``STOP``, ``RESTART``, ``RUNNING_FAILURE`` }.
    The use of this option is detailed in :ref:`conciliation`. |br|
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the conciliation phase
    would behave differently depending on which |Supvisors| instance is the *Master*.

    *Default*:  ``USER``.

    *Required*:  No.

    *Identical*:  Yes.

``disabilities_file``

    The file path that will be used to persist the program disabilities. This option has been added in support of the
    |Supervisor| request `#591 - New Feature: disable/enable <https://github.com/Supervisor/supervisor/issues/591>`_. |br|
    The persisted data will be serialized in a ``JSON`` string so a ``.json`` extension is recommended.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.

    .. hint::

        Both absolute and relative paths are supported. User expansion is also allowed. |br|
        It is expected that the folder tree exists. However |Supvisors| will try to create it if not,
        unless write permission is denied.

    .. note::

        If the file does not exist at startup, all processes are enabled by default and a first version of the file
        will be written down accordingly.

``stats_enabled``

    By default, |Supvisors| can provide basic statistics on the node and the processes spawned by |Supervisor|
    on the |Supvisors| :ref:`dashboard`, provided that the |psutil| module is installed. |br|
    This option can be used to adjust or disable the collection of the host and/or process statistics.
    Possible values are in { ``OFF``, ``HOST``, ``PROCESS``, ``ALL`` }. |br|
    For backwards compatibility, boolean values ``true`` and ``false`` have been kept and are respectively equal to
    ``ALL`` and ``OFF``.

    *Default*:  ``ALL``.

    *Required*:  No.

    *Identical*:  No.

``stats_collecting_period``

    This is the *minimum* duration between 2 statistics measurements on one entity (host or process).
    It is not a strict period. |br|
    Value in [``1`` ; ``3600``] seconds.

    *Default*:  ``10``.

    *Required*:  No.

    *Identical*:  No.

    .. note::

        The statistics collection is deferred to a dedicated process of |Supvisors|. The *Collector* is mainly
        using the |psutil| module. |br|
        Regardless of the number of processes to manage, the *Collector* will not take up more than one processor core.
        If there are more statistics requests than allowed by one processor core, the duration between 2 measurements
        on the same process will inevitably increase.

        If there are *many* processes to deal with and if it is unsuitable to dedicate one whole processor core
        to process statistics, the ``stats_collecting_period`` should be increased or the process statistics
        may be deactivated using the the ``stats_enabled`` option.

    .. attention::

        If there are multiple |Supvisors| instances on the same host, there will be multiple *Collector* processes too.
        The user should pay attention to set the ``stats_collecting_period`` option accordingly so that the CPU load
        remains within acceptable limits.


``stats_periods``

    The list of periods for which the statistics will be provided in the |Supvisors| :ref:`dashboard`, separated by
    commas. |br|
    Up to 3 int or float values are allowed in [``1`` ; ``3600``] seconds.

    *Default*:  ``10``.

    *Required*:  No.

    *Identical*:  No.

``stats_histo``

    The depth of the statistics history. |br|
    Value in [``10`` ; ``1500``].

    *Default*:  ``200``.

    *Required*:  No.

    *Identical*:  No.

``stats_irix_mode``

    The way of presenting process CPU values. |br|
    If ``true``, values are displayed in 'IRIX' mode. |br|
    If ``false``, values are displayed in 'Solaris' mode.

    *Default*:  ``false``.

    *Required*:  No.

    *Identical*:  No.

``tail_limit``

    In its Web UI, |Supervisor| provides a page that enables to display the 1024 latest bytes of the process logs.
    The page is made available by clicking on the process name in the process table. A button is added to refresh it.
    The size of the logs can be updated through the URL by updating the ``limit`` attribute. |br|
    The same function is provided in the |Supvisors| Web UI. This option has been added to enable a default size
    different than 1024 bytes. It applies to processes logs and |Supervisor| logs.

    *Default*:  ``1KB``.

    *Required*:  No.

    *Identical*:  No.

``tailf_limit``

    In its Web UI, |Supervisor| provides a page that enables to display the 1024 latest bytes of the process logs
    and that auto-refreshes the page in a ``tail -f`` manner. The page is made available by clicking on the ``Tail -f``
    button in the process table. The initial size of the logs cannot be updated. |br|
    The same function is provided in the |Supvisors| Web UI. This option has been added to enable a default size
    different than 1024 bytes. It applies to processes logs and |Supervisor| logs.

    *Default*:  ``1KB``.

    *Required*:  No.

    *Identical*:  No.

    .. attention::

        Setting the ``tail_limit`` and ``tailf_limit`` options with very big values may block the web browser. |br|
        Moderation should be considered.

The logging options are strictly identical to |Supervisor|'s. By the way, it is the same logger that is used.
These options are more detailed in
`supervisord Section values <http://supervisord.org/configuration.html#supervisord-section-values>`_.

``logfile``

    The path to the |Supvisors| activity log of the ``supervisord`` process. This option can include the value
    ``%(here)s``, which expands to the directory in which the |Supervisor| configuration file was found. |br|
    If ``logfile`` is unset or set to ``AUTO``, |Supvisors| will use the same logger as |Supervisor|. |br|
    It makes it easier to understand what happens when both |Supervisor| and |Supvisors| log in the same file.

    *Default*:  ``AUTO``.

    *Required*:  No.

    *Identical*:  No.

``logfile_maxbytes``

    The maximum number of bytes that may be consumed by the |Supvisors| activity log file before it is rotated
    (suffix multipliers like ``KB``, ``MB``, and ``GB`` can be used in the value). |br|
    Set this value to ``0`` to indicate an unlimited log size. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``50MB``.

    *Required*:  No.

    *Identical*:  No.

``logfile_backups``

    The number of backups to keep around resulting from |Supvisors| activity log file rotation. |br|
    If set to ``0``, no backups will be kept. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``10``.

    *Required*:  No.

    *Identical*:  No.

``loglevel``

    The logging level, dictating what is written to the |Supvisors| activity log. |br|
    One of [``critical``, ``error``, ``warn``, ``info``, ``debug``, ``trace``,  ``blather``]. |br|
    See also: `supervisord Activity Log Levels <http://supervisord.org/logging.html#activity-log-levels>`_. |br|
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
    software_name = Supvisors Tests
    software_icon = ../ui/img/icon.png
    supvisors_list = cliche81,<cliche82>192.168.1.49,cliche83:60000:60001,cliche84
    rules_files = ./etc/my_movies*.xml
    stereotypes = @TEST
    auto_fence = false
    event_link = WS
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
    tail_limit = 50MB
    tailf_limit = 50MB
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
    different |Supvisors| instances, |Supvisors| will consider this as a conflict. |br|
    Only the *Managed* applications have an entry in the navigation menu of the |Supvisors| Web UI.

    The groups declared in |Supervisor| configuration files and not declared in a rules file will thus be considered
    as *Unmanaged* by |Supvisors|. So they have no entry in the navigation menu of the |Supvisors| web page. |br|
    There can be as many running instances of the same program as |Supervisor| allows over the available |Supvisors|
    instances.

If the |lxml| package is available on the system, |Supvisors| uses it to validate the XML rules files
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

    A regex matching one or more |Supervisor| group names is expected in this attribute. |br|
    Refer to `Using patterns`_ for more details.

    *Default*:  None.

    *Required*:  Yes, unless a ``name`` attribute is provided.

.. note::

    The options below can be declared in any order in the ``application`` section.

``distribution``

    In the introduction, it is written that the aim of |Supvisors| is to manage distributed applications. |br|
    However, it may happen that some applications are not designed to be distributed (for example due to inter-process
    communication design) and thus distributing the application processes over multiple nodes would just make
    the application non operational. |br|
    If set to ``ALL_INSTANCES``, |Supvisors| will distribute the application processes over the applicable |Supvisors|
    instances. |br|
    If set to ``SINGLE_INSTANCE``, |Supvisors| will start all the application processes in the same |Supvisors|
    instance. |br|
    If set to ``SINGLE_NODE``, |Supvisors| will distribute all the application processes over a set of |Supvisors|
    instances running on the same node.

    *Default*:  ``ALL_INSTANCES``.

    *Required*:  No.

.. note::

    When a single |Supvisors| instance is running on each node, ``SINGLE_INSTANCE`` and ``SINGLE_NODE`` are strictly
    equivalent.

``identifiers``

    This element is only used when ``distribution`` is set to ``SINGLE_INSTANCE`` or ``SINGLE_NODE`` and gives the list
    of |Supvisors| instances where the application programs can be started.

    The names are to be taken either the names deduced from the ``supvisors_list`` option defined
    in `rpcinterface extension point`_, and / or from the declared `Instance aliases`_, and / or or from a stereotype
    as provided in the ``stereotypes`` option, and separated by commas.

    Special values can be used. |br|
    The *wildcard symbol* ``*`` stands for all names deduced from ``supvisors_list``. |br|
    Any name list including a ``*`` is strictly equivalent to ``*`` alone.

    The *hashtag symbol* ``#`` can be used with a ``pattern`` definition and eventually complemented by a list
    of deduced names. |br|
    The aim is to assign the Nth deduced name of ``supvisors_list`` or the Nth name of the subsequent list
    (made of names deduced from ``supvisors_list``) to the Nth instance of the application, **assuming that 'N' is
    provided at the end of the application name, preceded by a dash or an underscore**. |br|
    Yeah, a bit tricky to explain... Examples will be given in `Using patterns and signs`_.

    *Default*:  ``*``.

    *Required*:  No.

.. attention::

    When the distribution of the application is restricted (``distribution`` not set to ``ALL_INSTANCES``), the rule
    ``identifiers`` of the application programs is not considered.

``start_sequence``

    This element gives the starting rank of the application in the ``DISTRIBUTION`` state,
    when applications are started automatically. |br|
    When <= ``0``, the application is not started. |br|
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

    The strategy used to start applications on |Supvisors| instances. |br|
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` }. |br|
    The use of this option is detailed in :ref:`starting_strategy`.

    *Default*:  the value set in the :ref:`supvisors_section` of the |Supervisor| configuration file.

    *Required*:  No.

``starting_failure_strategy``

    This element gives the strategy applied upon a major failure, i.e. happening on a required process,
    in the starting phase of an application. |br|
    The possible values are { ``ABORT``, ``STOP``, ``CONTINUE`` } and are detailed in :ref:`starting_failure_strategy`.

    *Default*:  ``ABORT``.

    *Required*:  No.

``running_failure_strategy``

    This element gives the strategy applied when the application loses running processes due to a |Supvisors| instance
    that becomes silent (crash, power down, network failure, etc). |br|
    This value can be superseded by the value set at program level. |br|
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION``,
    ``SHUTDOWN``, ``RESTART`` }
    and are detailed in :ref:`running_failure_strategy`.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

``operational_status``

    This element contains the formula that will be used to evaluate the operational status of the application,
    displayed in the |Supvisors| Web UI, and has no other impact on any |Supvisors| function.
    The formula will be parsed using the Python module ``AST``. The exhaustive list of operators and functions
    supported by |Supvisors| is: ``and``, ``or``, ``not``, ``any`` and ``all``. Parenthesis can also be used. |br|
    The operands must be string values, between quotes or double-quotes, corresponding to a program name
    of the application, or a pattern matching one or multiple program names. Multiple program names must be used as
    an argument of ``any`` or ``all``. |br|
    When set, the ``required`` value of the  ``programs`` elements is not considered.

    *Default*:  None.

    *Required*:  No.

``programs``

    This element is the grouping section of all ``program`` rules that are applicable to the application. |br|
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

The ``program`` element defines the rules applicable to at least one program. This element must be included in an
``programs`` element. |br|
Here follows the definition of the attributes and rules applicable to this element.

.. note::

    The options below can be declared in any order in the ``program`` section.

``name``

    This attribute MUST match exactly the name of a program as defined in
    `Supervisor program settings <http://supervisord.org/configuration.html#program-x-section-settings>`_.

    *Default*:  None.

    *Required*:  Yes, unless an attribute ``pattern`` is provided.

``pattern``

    A regex matching one or more |Supervisor| program names is expected in this attribute. |br|
    Refer to the `Using patterns`_ for more details.

    *Default*:  None.

    *Required*:  Yes, unless an attribute ``name`` is provided.

``identifiers``

    This element gives the list of |Supvisors| instances where the program can be started.

    The names are separated by commas and have to be taken from:

        * either the names declared in the ``supvisors_list`` option defined in the `rpcinterface extension point`_,
        * and / or the declared `Instance aliases`_,
        * and / or a stereotype provided in the ``stereotypes`` option.

    Special values can be applied. |br|
    The *wildcard symbol* ``*`` stands for all names deduced from ``supvisors_list``. |br|
    Any name list including a ``*`` is strictly equivalent to ``*`` alone. |br|

    The *hashtag symbol* ``#`` and the *at symbol* ``@`` can be used with a ``pattern`` definition and eventually
    complemented by a list of deduced names. |br|
    The aim is to assign the Nth deduced name of ``supvisors_list`` or the Nth name of the subsequent list (made of
    names deduced from ``supvisors_list``) to the Nth instance of the program in a homogeneous process group. |br|
    Examples will be given in `Using patterns and signs`_.

    *Default*:  ``*``.

    *Required*:  No.

``required``

    This element gives the importance of the program for the application. |br|
    If ``true`` (resp. ``false``), a failure of the program is considered major (resp. minor). |br|
    When the ``operational_status`` element of the  ``application`` element is set, this element is ignored. |br|
    This information is mainly used to give the operational status of the application in the Web UI and has no other
    impact on any |Supvisors| function.

    *Default*:  ``false``.

    *Required*:  No.

``start_sequence``

    This element gives the starting rank of the program when the application is starting. |br|
    When <= ``0``, the program is not started automatically. |br|
    When > ``0``, the program is started automatically in the given order.

    *Default*:  ``0``.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the program when the application is stopping. |br|
    This value must be positive. If not set, it is defaulted to the ``start_sequence`` value. |br|
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
    in terms of resources (CPU, memory, network) is in the user's hands. |br|
    When multiple |Supvisors| instances are available, |Supvisors| uses the ``expected_loading`` value to distribute
    the processes over the available |Supvisors| instances, so that the system remains safe.

    *Default*:  ``0``.

    *Required*:  No.

    .. note:: *About the choice of an user estimation*

        Although |Supvisors| may be taking measurements on each node where it is running, it has been chosen not to use
        these figures for the loading purpose. Indeed, the resources consumption of a process may be very variable
        in time and is not foreseeable. |br|
        It is recommended to give a value based on an average usage of the resources in the worst case
        configuration and to add a margin corresponding to the standard deviation.

``starting_failure_strategy``

    This element gives the strategy applied upon a major failure, i.e. happening on a required process,
    in the starting phase of an application. This value supersedes the value eventually set at application level. |br|
    The possible values are { ``ABORT``, ``STOP``, ``CONTINUE`` } and are detailed in :ref:`starting_failure_strategy`.

    *Default*:  ``ABORT``.

    *Required*:  No.

``running_failure_strategy``

    This element gives the strategy applied when the process is running in a |Supvisors| instance that becomes silent
    (crash, power down, network failure, etc). This value supersedes the value eventually set at application level. |br|
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

        The ``reference`` element can be combined with all the other elements described above. |br|
        The rules got from the referenced model are loaded first and then eventually superseded by any other rule
        defined in the same program section. |br|
        A model can reference another model. In order to prevent infinite loops and to keep a reasonable complexity,
        the maximum chain starting from the ``program`` section has been set to 3. |br|
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

It may be quite tedious to give all this information to every program, especially if multiple programs use a common
set of rules. So two mechanisms are put in place to help.

The first one is the ``pattern`` attribute that may be used instead of the ``name`` attribute in a ``program`` element.
It can be used to configure a set of programs in a more flexible way than just considering homogeneous programs,
like |Supervisor| does.

The same ``program`` options are applicable, whatever a ``name`` attribute or a ``pattern`` attribute is used. |br|
For a ``pattern`` attribute, a regex (or a simple substring) matching one |Supervisor| program name or more is expected.

.. code-block:: xml

    <program pattern="prg_">
        <identifiers>cliche01,cliche03,cliche02</identifiers>
        <start_sequence>2</start_sequence>
        <required>true</required>
    </program>

.. attention:: *About the pattern names*.

    Precautions must be taken when using a ``pattern`` definition. |br|
    In the previous example, the rules are applicable to every program names containing the ``"prg_"`` substring,
    so that it matches :program:`prg_00`, :program:`prg_dummy`, but also :program:`dummy_prg_2`.

    As a general rule when looking for program rules, |Supvisors| always searches for a ``program`` definition having
    the exact program name set in the ``name`` attribute, and only if not found, |Supvisors| tries to find a
    corresponding ``program`` definition with a matching ``pattern``.

    It also may happen that multiple patterns match the same program name. In this case, |Supvisors| chooses the
    pattern with the greatest matching, or arbitrarily the first of them if such a rule does not discriminate enough. |br|
    So considering the program :program:`prg_00` and the two matching patterns ``prg`` and ``prg_``, |Supvisors| will
    apply the rules related to ``prg_``.

The ``pattern`` attribute can be applied to ``application`` elements too. The same logic as per ``program`` elements
applies. This is particularly useful in a context where many users over multiple nodes need to have
their own application.

.. note::

    |Supervisor| does not provide support for *homogeneous* groups of *heterogeneous* programs. |br|
    So in order to have N running instances of the same application, the only possible solution is to define N times
    the |Supervisor| group using a variation in the group name (e.g. an index suffix). |br|
    It is however possible to include the same |Supervisor| program definitions into different groups.

    Unfortunately, using *homogeneous* program groups with ``numprocs`` set to N cannot help in the present case
    because |Supervisor| considers the program name in the group and not the ``process_name``.


.. _patterns_hashtags:

Using patterns and signs
~~~~~~~~~~~~~~~~~~~~~~~~

The *hashtag symbol* ``#`` and *at symbol* in the program ``identifiers`` are designed for a program that is meant
to be started on every |Supvisors| instance available, or on a subset of them.

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

    When using the |Supvisors| discovery mode is activated, the |Supvisors| instances are chosen in accordance with
    their arrival in the system, which is random but fixed when established.

    The start index defined in ``numprocs_start`` has no consequence.

.. important::

    In the initial |Supvisors| design, it was expected that the ``numprocs`` value set in the program configuration file
    would exactly match the number of |Supvisors| instances.

    However, if the number of |Supvisors| instances is greater than the ``numprocs`` value, processes will be assigned
    to the ``numprocs`` first |Supvisors| instances, with both ``#`` and ``@``.

    On the other side, if the number of |Supvisors| instances is lower than the ``numprocs`` value:

        - when using ``@``, one process will be assigned to each |Supvisors| instance, leaving the processes in excess
          unassigned ;
        - when using ``#``, all the processes will be equally assigned on the |Supvisors| instances.

.. attention::

    As pointed out just before, |Supvisors| takes the information from the program configuration. So this function
    will definitely NOT work if the program is unknown to the local |Supervisor|, which is a relevant use case. |br|
    As written before, the |Supervisor| configuration can be different for all |Supvisors| instances, including
    the definition of groups and programs.

.. important:: *Convention for application names when using patterns and signs*

    When the hashtag is used for the application ``identifiers``, |Supvisors| cannot rely on the |Supervisor|
    configuration to map the application instances to the |Supvisors| instances.

    By convention, the application name MUST end with ``-N`` or ``_N``. The Nth application will be mapped to the Nth
    deduced name of the list, i.e. the name at index ``N-1`` in the list.

    ``N`` must be strictly positive. Zero-padding is allowed, as long as ``N`` can be converted into an integer.


``<model>`` rules
~~~~~~~~~~~~~~~~~

The second mechanism is the ``model`` definition. |br|
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
            <operational_status>all('.*')</operational_status>

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
            <operational_status>all("register.*") and any('movie.*')</operational_status>

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
