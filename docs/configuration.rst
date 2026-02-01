.. _configuration:

Supervisor Configuration File
=============================

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


.. _supvisors_identifiers:

Supvisors instance identification
---------------------------------

.. important::

    This section is key for the user to understand how |Supvisors| works, and how to configure |Supvisors|. |br|
    Indeed, dealing with distributed applications involves certain network-related aspects.

First it is important to remind that every Node has a distinct network configuration. Host names are not
necessarily identically declined in all of them. Network interfaces may also be different from one Node to the other.

.. important::

    When configuring |Supvisors| with multiple |Supvisors| instances, special attention should be paid to ensuring
    that all |Supvisors| instances can communicate with each other from a network perspective.

That said, every |Supvisors| instance identifies itself using an identifier, a.k.a. |Supvisors| identifier,
under the form ``host_id:http_port``, and builds |Supvisors| identifiers to identify the other |Supvisors| instances
it is aware of, in accordance with the |Supvisors| configuration that will be addressed in this page.

``host_id`` corresponds to the Node where the |Supvisors| instance is running. It can be a host name, a fully qualified
domain name, a Node alias or an IPv4 address.

``http_port`` is the port of the internet socket used to communicate with the |Supervisor| instance (obviously unique
per Node).

As a general rule, the |Supvisors| identifier is the key used to exchange information between the |Supvisors| instances.

In addition to the |Supvisors| identifier, an optional ``nick_identifier``, a.k.a. |Supvisors| nickname, may be set:

    * either directly set by the user in the |Supvisors| option ``supvisors_list``,
    * or taken from the |Supervisor| identifier,
    * or defaulted with the |Supvisors| identifier.

.. hint::

    The |Supervisor| identifier can either be set in the ``supervisord`` section of the |Supervisor| configuration file,
    or in the command line when starting the :command:`supervisord` program.

The |Supvisors| nickname is generally used in place of the |Supvisors| identifier in the |Supvisors| Web UI and
in the log traces.

The |Supvisors| nickname can be used as an alternative of the |Supvisors| identifier:

    * in some options of the ``[supvisors]`` section of the |Supervisor| configuration file,
    * in the :ref:`rules_file`,
    * in the :ref:`xml_rpc`,
    * in the ``supervisorctl`` commands.


.. _supvisors_section:

rpcinterface extension point
----------------------------

|Supvisors| extends the `Supervisor's XML-RPC API <http://supervisord.org/xmlrpc.html>`_.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

The parameters of |Supvisors| are set in this section of the |Supervisor| configuration file.
It is expected that some parameters are strictly identical for all |Supvisors| instances otherwise unpredictable
behavior may happen. The present section details where it is applicable.

``supvisors_list``

    The list of |Supvisors| instances that constitute |Supvisors|, separated by commas. |br|
    The elements of ``supvisors_list`` define how the |Supvisors| instances will share information between them
    and MUST be identical to all |Supvisors| instances or unpredictable behavior may happen.

    The exhaustive form of an element matches ``<nick_identifier>host_id:http_port``, where:

        * ``nick_identifier`` is the optional |Supvisors| nickname ;
        * ``host_id:http_port`` is the |Supvisors| identifier, as described in the previous section.

    *Default*:  the host name, as given by the ``socket.gethostname()`` function.

    *Required*:  No.

    *Identical*:  Yes.

    .. important::

        When multiple entries are provided, the local |Supvisors| instance must identify itself in exactly one element
        of the list. To that end, |Supvisors| tries to match the ``host_id`` of these items with a comprehensive picture
        of the network, as perceived by the local host, and to match the ``http_port`` with the HTTP port of the
        local |Supervisor| instance.

    .. attention::

        if ``http_port`` is not provided, the local |Supvisors| instance takes the assumption that the targeted
        |Supvisors| instance uses the same ``http_port`` as the local |Supvisors| instance. |br|
        The ``http_port`` *MUST* be set if multiple |Supvisors| instances are running on the same node.

    .. hint::

        If the |Supvisors| is configured with at most one |Supvisors| instance per host, the ``host_id`` alone is a
        fully acceptable declaration.

``software_name``

    An optional string that will be displayed at the top of the |Supvisors| Web UI. It is intended to correspond to
    the name of the user software.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.

``software_icon``

    An optional image that will be displayed at the top of the |Supvisors| Web UI. It is intended to correspond to
    the icon of the user software.

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
    Instead of ``ini`` files, XML rules files are expected here. Their content is described in :ref:`rules_file`. |br|
    It is highly recommended that this parameter is identical to all |Supvisors| instances or the startup sequence would
    be different depending on which |Supvisors| instance is given the *Master* role.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

``css_files``

    A space-separated sequence of file globs, in the same vein as
    `supervisord include section <http://supervisord.org/configuration.html#include-section-values>`_.
    Instead of ``ini`` files, CSS files are expected here. |br|
    The content of these CSS files is added after the |Supvisors| CSS files, so that the user can override
    the |Supvisors| Web UI style.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  No.

``auto_fence``

    When true, |Supvisors| will definitely disconnect a |Supvisors| instance that is inactive. |br|
    This functionality is detailed in :ref:`auto_fencing`. |br|
    This parameter must be identical to all |Supvisors| instances. If any inconsistency is detected, the |Supvisors|
    instances will isolate each other.

    *Default*:  ``false``.

    *Required*:  No.

    *Identical*:  Yes.


``event_link``

    The communication protocol type used to publish all |Supvisors| events (Instance, Application
    and Process events). |br|
    Value in [``NONE`` ; ``ZMQ`` ; ``WS``]. Other protocols may be considered in the future. |br|
    If set to ``NONE``, the interface is not available. |br|
    If set to ``ZMQ``, events are published through a |ZeroMQ| TCP socket. |br|
    If set to ``WS``, events are published through |Websockets|. |br|
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

    The conditions applied by |Supvisors| to exit the ``SYNCHRONIZATION`` state. |br|
    Multiple values in [``LIST`` ; ``TIMEOUT`` ; ``CORE`` ; ``USER``], separated by commas. |br|
    If ``STRICT`` is selected, |Supvisors| exits the ``SYNCHRONIZATION`` state when all the |Supvisors| instances
    declared in the ``supvisors_list`` option are in the ``RUNNING`` state. |br|
    If ``LIST`` is selected, |Supvisors| exits the ``SYNCHRONIZATION`` state when all known |Supvisors| instances
    (including those declared in the ``supvisors_list`` option **AND** those discovered) are in the ``RUNNING`` state.
    If ``TIMEOUT`` is selected, |Supvisors| exits the ``SYNCHRONIZATION`` state after the duration defined in the
    ``synchro_timeout`` option. |br|
    If ``CORE`` is selected, |Supvisors| exits the ``SYNCHRONIZATION`` state when all the |Supvisors| instances
    identified in the ``core_identifiers`` option are in the ``RUNNING`` state. |br|
    If ``USER`` is selected, |Supvisors| exits the ``SYNCHRONIZATION`` state as soon as the *Master* instance is set,
    which can be triggered upon user request (using the |Supvisors| Web UI, the ``end_sync`` XML-RPC or the ``end_sync``
    command of ``supervisorctl``). |br|
    The use of this option is more detailed in :ref:`synchronizing`.

    *Default*:  ``STRICT,TIMEOUT,CORE``.

    *Required*:  No.

    *Identical*:  No.

``synchro_timeout``

    The time in seconds that |Supvisors| waits for all expected |Supvisors| instances to publish their TICK.
    Value in [``0`` ; ``1200``]. |br|
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

    A list of |Supvisors| identifiers, nicknames or stereotypes, separated by commas. |br|
    If the |Supvisors| instances of this subset are all in a ``RUNNING`` state and the ``CORE`` value is set
    in the ``synchro_options`` option, this will put an end to the ``SYNCHRONIZATION`` state in |Supvisors|. |br|
    Independently from the ``CORE`` option being set, |Supvisors| will preferably take a member of this list when
    selecting a *Master* instance. |br|
    This parameter must be identical to all |Supvisors| instances or unpredictable behavior will happen.

    *Default*:  None.

    *Required*:  No.

    *Identical*:  Yes.

.. attention::

    The following combination will cause unpredictable behavior, and will lead to |Supvisors| conflicts:

        * discovery mode is enabled,
        * ``CORE`` is set in ``synchro_options``,
        * stereotypes are used in the ``core_identifiers`` option,
        * discovered |Supvisors| instances have the stereotype used.


``supvisors_failure_strategy``

    This provides |Supvisors| with a strategy to apply used when the conditions implied by the ``synchro_options``
    are not met anymore, e.g. when a |Supvisors| *Core* instance becomes inactive. |br|
    Possible values are in { ``CONTINUE``, ``RESYNC``, ``SHUTDOWN``}. |br|
    If ``CONTINUE`` is selected, |Supvisors| will deal with the missing |Supvisors| instance and continue
    in a degraded mode. |br|
    If ``RESYNC`` is selected, |Supvisors| will transition back to the ``SYNCHRONIZATION`` state and wait
    for the selected conditions to be met again. |br|
    If ``SHUTDOWN`` is selected, |Supvisors| will shut down. |br|
    This parameter must be identical to all |Supvisors| instances. If any inconsistency is detected, the |Supvisors|
    instances will isolate each other.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

    *Identical*:  Yes.

``starting_strategy``

    The strategy used to start applications on |Supvisors| instances. |br|
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` , ``LESS_LOADED_NODE``,
    ``MOST_LOADED_NODE``}. |br|
    The use of this option is detailed in :ref:`starting_strategy`. |br|
    This parameter must be identical to all |Supvisors| instances. If any inconsistency is detected, the |Supvisors|
    instances will isolate each other.

    *Default*:  ``CONFIG``.

    *Required*:  No.

    *Identical*:  Yes.

``conciliation_strategy``

    The strategy used to solve conflicts upon detection that multiple instances of the same program are running. |br|
    Possible values are in { ``SENICIDE``, ``INFANTICIDE``, ``USER``, ``STOP``, ``RESTART``, ``RUNNING_FAILURE`` }.
    The use of this option is detailed in :ref:`conciliation`. |br|
    This parameter must be identical to all |Supvisors| instances. If any inconsistency is detected, the |Supvisors|
    instances will isolate each other.

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
        It is expected that the folder tree exists. However |Supvisors| will try to create it if absent,
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

    .. important::

        |Supvisors| collect the process statistics considering the process spawned by |Supervisor| and its children.
        In the event where the program command starts a process that is not attached to the command itself
        (e.g. a Docker container), the process statistics will NOT take into account this process and its children.

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

    |Supervisor| provides a Web UI page that enables to display the 1024 latest bytes of the process logs
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
-------------------------

|Supvisors| also extends `supervisorctl <http://supervisord.org/running.html#running-supervisorctl>`_.
This feature is not described in |Supervisor| documentation.

.. code-block:: ini

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


Configuration File Example
--------------------------

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

.. include:: common.rst
