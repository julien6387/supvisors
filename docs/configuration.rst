.. _configuration:

Configuration
=============

Supervisor's Configuration File
---------------------------------

This section explains how |Supvisors| uses and complements the
`Supervisor configuration <http://supervisord.org/configuration.html>`_.

.. _supvisors_section:

rpcinterface extension point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|Supvisors| extends the `Supervisor's XML-RPC API <http://supervisord.org/xmlrpc.html>`_.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

The parameters of |Supvisors| are set in this section of the |Supervisor| configuration file.
It is expected that all |Supvisors| *instances* use the same configuration (excluding included files and logger
parameters) or it may lead to unpredictable behavior.

``address_list``

    The list of node names where |Supvisors| will be running, separated by commas.

    *Default*:  the local host name.

    *Required*:  No.

    .. attention::

        The node names are expected to be known to every nodes in the list.
        If it's not the case, check the network configuration.

    .. hint::

        If the `psutil <https://pypi.python.org/pypi/psutil>`_ package is installed, it is possible to use
        IP addresses in addition to node names.

        Like the node names, the IP addresses are expected to be known to every nodes in the list.
        If it's not the case, check the network configuration.


``rules_files``

    A list of paths to XML rules files, in the same format as the one used for
    `supervisord include section <http://supervisord.org/configuration.html#include-section-values>`_.
    Their content is described in `Supvisors' Rules File`_.

    *Default*:  None.

    *Required*:  No.

``auto_fence``

    When true, |Supvisors| won't try to reconnect to a |Supvisors| instance that is inactive.
    This functionality is detailed in :ref:`auto_fencing`.

    *Default*:  ``false``.

    *Required*:  No.

``internal_port``

    The internal port number used to publish local events to remote |Supvisors| instances.
    Events are published through a PyZMQ TCP socket.

    *Default*:  ``65001``.

    *Required*:  No.


``event_port``

    The port number used to publish all |Supvisors| events (Address, Application and Process events).
    Events are published through a PyZMQ TCP socket. The protocol of this interface is explained
    in :ref:`event_interface`.

    *Default*:  ``65002``.

    *Required*:  No.

``synchro_timeout``

    The time in seconds that |Supvisors| waits for all expected |Supvisors| instances to publish.
    Value in [``15`` ; ``1200``].
    This use of this option is detailed in :ref:`synchronizing`.

    *Default*:  ``15``.

    *Required*:  No.

``force_synchro_if``

    A subset of ``address_list``, separated by commas. If the nodes of this subset are all ``RUNNING``, this will put
    an end to the synchronization phase in |Supvisors|.
    If not set, |Supvisors| waits for all expected |Supvisors| instances to publish until ``synchro_timeout``.

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

    The list of periods for which the statistics will be provided in the |Supvisors| :ref:`dashboard`, separated by
    commas. Up to 3 values are allowed in [``5`` ; ``3600``] seconds, each of them MUST be a multiple of 5.

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

``logfile_maxbytes``

    The maximum number of bytes that may be consumed by the |Supvisors| activity log file before it is rotated
    (suffix multipliers like ``KB``, ``MB``, and ``GB`` can be used in the value).
    Set this value to ``0`` to indicate an unlimited log size. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``50MB``.

    *Required*:  No.

``logfile_backups``

    The number of backups to keep around resulting from |Supvisors| activity log file rotation.
    If set to ``0``, no backups will be kept. No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``10``.

    *Required*:  No.

``loglevel``

    The logging level, dictating what is written to the |Supvisors| activity log.
    One of [``critical``, ``error``, ``warn``, ``info``, ``debug``, ``trace``,  ``blather``].
    See also: `supervisord Activity Log Levels <http://supervisord.org/logging.html#activity-log-levels>`_.
    No effect if ``logfile`` is unset or set to ``AUTO``.

    *Default*:  ``info``.

    *Required*:  No.


ctlplugin extension point
~~~~~~~~~~~~~~~~~~~~~~~~~

|Supvisors| extends also `supervisorctl <http://supervisord.org/running.html#running-supervisorctl>`_.
This feature is not described in |Supervisor| documentation.

.. code-block:: ini

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


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
    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    address_list = cliche01,cliche03,cliche02,cliche04
    rules_file = ./etc/my_movies.xml
    auto_fence = false
    internal_port = 60001
    event_port = 60002
    synchro_timeout = 20
    starting_strategy = LESS_LOADED
    conciliation_strategy = INFANTICIDE
    stats_periods = 5,60,600
    stats_histo = 100
    logfile = ./log/supvisors.log
    logfile_maxbytes = 50MB
    logfile_backups = 10
    loglevel = info

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


.. _rules_file:

|Supvisors|' Rules File
--------------------------

This part describes the contents of the XML rules file declared in the ``rules_file`` option.

Basically, the rules file contains rules that define how applications and programs should be started and stopped,
and the quality of service expected. It relies on the |Supervisor| group and program definitions.

.. important:: *About the declaration of Supervisor groups/processes in the rules file*

    It is important to notice that all applications declared in this file will be considered as *Managed*
    by |Supvisors|. The main consequence is that |Supvisors| will try to ensure that one single instance of the program
    is running over all the nodes considered. If two instances of the same program are running on two different nodes,
    |Supvisors| will consider this as a conflict. Only the *Managed* applications have an entry in the navigation menu
    of the |Supvisors| web page.

    The groups declared in |Supervisor| configuration files and not declared in the rules file will thus be considered
    as *Unmanaged* by |Supvisors|. So they have no entry in the navigation menu of the |Supvisors| web page.
    There can be as many running instances of the same program as |Supervisor| allows over the available nodes.

If the `lxml <http://lxml.de>`_ package is available on the system, |Supvisors| uses it to validate
the XML rules file before it is used.

.. hint::

    It is still possible to validate the XML rules file manually. The XSD file :file:`rules.xsd` used to validate the
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

    A substring matching one or more |Supervisor| group names is expected in this attribute.
    Refer to `Using patterns`_ for more details.

    *Default*:  None.

    *Required*:  Yes, unless a ``name`` attribute is provided.

``distributed``

    In the introduction, it is written that the aim of |Supvisors| is to manage distributed applications.
    However, it may happen that some applications are not designed to be distributed (for example due to inter-process
    communication design) and thus distributing the application processes over a set of nodes would just make
    the application non operational.
    If set to ``true``, |Supvisors| will start all the application processes on the same node, provided that a node
    can be found based on the application rules ``starting_strategy`` and ``addresses``.

    *Default*:  ``true``.

    *Required*:  No.

``addresses``

    This element is only used when ``distributed`` is set to ``false`` and gives the list of nodes where the application
    programs can be started. The node names are to be taken from the ``address_list`` defined in
    `rpcinterface extension point`_ or from the declared `Node aliases`_, and separated by commas.
    Special values can be applied.

    The wildcard ``*`` stands for all node names in ``address_list``.
    Any node list including a ``*`` is strictly equivalent to ``*`` alone.

    The hashtag ``#`` can be used in a ``pattern`` definition and eventually complemented by a list of nodes.
    The aim is to assign the Nth node of either ``address_list`` or of the subsequent node list to the Nth instance
    of the application, **assuming that 'N' is provided at the end of the application name, preceded by a dash or
    an underscore**.
    An example will be given in `Using patterns and hashtags`_.

    *Default*:  ``*``.

    *Required*:  No.

.. note::

    When the application is not to be distributed (``distributed`` set to ``false``), the rule ``addresses`` of the
    application programs is not considered.


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

    The strategy used to start applications on nodes.
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` }.
    The use of this option is detailed in :ref:`starting_strategy`.

    *Default*:  the value set in the :ref:`supvisors_section` of the |Supervisor| configuration file.

    *Required*:  No.

``starting_failure_strategy``

    This element gives the strategy applied upon a major failure in the starting phase of an application.
    The possible values are { ``ABORT``, ``STOP``, ``CONTINUE`` } and are detailed in :ref:`starting_failure_strategy`.

    *Default*:  ``ABORT``.

    *Required*:  No.

``running_failure_strategy``

    This element gives the strategy applied when the application loses running processes due to a node that becomes
    silent (crash, power down, network failure, etc). This value can be superseded by the value set at program level.
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION`` }
    and are detailed in :ref:`running_failure_strategy`.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

``program``

    This element defines the rules that are applicable to the program whose name matches the ``name`` or ``pattern``
    attribute of the element. The ``name`` must match exactly a program name
    in the program list of the
    `Supervisor group definition <http://supervisord.org/configuration.html#group-x-section-settings>`_
    for the application considered here.
    Obviously, the definition of an application can include multiple ``program`` elements.

    *Default*:  None.

    *Required*:  No.


``<program>`` rules
~~~~~~~~~~~~~~~~~~~

The ``program`` element defines the rules applicable to at least one program. This element must be included in an
``application`` element. Here follows the definition of the attributes and rules applicable to this element.

``name``

    This attribute MUST match exactly the name of a program as defined in
    `Supervisor program settings <http://supervisord.org/configuration.html#program-x-section-settings>`_.

    *Default*:  None.

    *Required*:  Yes, unless an attribute ``pattern`` is provided.

``pattern``

    A substring matching one or more |Supervisor| program names is expected in this attribute.
    Refer to the `Using patterns`_ for more details.

    *Default*:  None.

    *Required*:  Yes, unless an attribute ``name`` is provided.

``addresses``

    This element gives the list of nodes where the program can be started. The node names are to be taken from
    the ``address_list`` defined in `rpcinterface extension point`_ or from the declared `Node aliases`_,
    and separated by commas. Special values can be applied.

    The wildcard ``*`` stands for all node names in ``address_list``.
    Any node list including a ``*`` is strictly equivalent to ``*`` alone.

    The hashtag ``#`` can be used in a ``pattern`` definition and eventually complemented by a list of nodes.
    The aim is to assign the Nth node of either ``address_list`` or the subsequent node list to the Nth instance
    of the program in a homogeneous process group. An example will be given in `Using patterns and hashtags`_.

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

    When multiple nodes are available, |Supvisors| uses the ``expected_loading`` value to distribute the processes over
    the available nodes, so that the system remains safe.

    *Default*:  ``0``.

    *Required*:  No.

    .. note:: *About the choice of an user estimation*

        Although |Supvisors| may be taking measurements on each node where it is running, it has been chosen not to use
        these figures for the loading purpose. Indeed, the resources consumption of a process may be very variable
        in time and is not foreseeable.

        It is recommended to give a value based on an average usage of the resources in the worst case
        configuration and to add a margin corresponding to the standard deviation.

``running_failure_strategy``

    This element gives the strategy applied when the process is running on a node that becomes silent (crash, power
    down, network failure, etc). This value supersedes the value set at application level.
    The possible values are { ``CONTINUE``, ``RESTART_PROCESS``, ``STOP_APPLICATION``, ``RESTART_APPLICATION`` }
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
        <addresses>cliche01,cliche03,cliche02</addresses>
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
For a ``pattern`` attribute, a substring matching one |Supervisor| program name or more is expected.

.. code-block:: xml

    <program pattern="prg_">
        <addresses>cliche01,cliche03,cliche02</addresses>
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

    It also may happen that several patterns match the same program name. In this case, |Supvisors| chooses the
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

    As it may be a bit clumsy to define the N definition sets, a script :command:`supvisors_breed` is provided in
    |Supvisors| package to help the user to duplicate an application from a template.
    Use examples can be found in the |Supvisors| use cases :ref:`scenario_2` and :ref:`scenario_3`.


.. _patterns_hashtags:

Using patterns and hashtags
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using a hashtag ``#`` in the program ``addresses`` is designed for a program that is meant to be started on every nodes
of the node list, or on a subset of them.

As an example, based on the following simplified |Supervisor| configuration:

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    address_list = cliche01,cliche02,cliche03,cliche04,cliche05

    [program:prg]
    process_name=prg_%(process_num)02d
    numprocs=5
    numprocs_start=1

Without this option, it is necessary to define rules for all instances of the program.

.. code-block:: xml

    <program name="prg_01">
        <addresses>cliche01</addresses>
    </program>

    <!-- similar definitions for prg_02, prg_03, prg_04 -->

    <program name="prg_05">
        <addresses>cliche05</addresses>
    </program>

Now with this option, the rule becomes more simple.

.. code-block:: xml

    <program pattern="prg_">
        <addresses>#</addresses>
    </program>

It is also possible to give a subset of nodes only.

.. code-block:: xml

    <program pattern="prg_">
        <addresses>#,cliche04,cliche02</addresses>
    </program>

.. note::

    Nodes are chosen in accordance with the sequence given in ``address_list`` or in the subsequent list.
    In the second example above, :program:`prg_01` will be assigned to ``cliche04`` and :program:`prg_02` to
    ``cliche02``.

    |Supvisors| does take into account the start index defined in ``numprocs_start``.

.. important::

    In the program configuration file, it is expected that the ``numprocs`` value matches the number of elements in
    ``address_list``.

    If the number of nodes in ``address_list`` is greater than the ``numprocs`` value, programs will
    be assigned to the ``numprocs`` first nodes.

    On the other side, if the number of nodes in ``address_list`` is lower than the ``numprocs`` value,
    the last programs won't be assigned to any node and it won't be possible to start them using |Supvisors|,
    as the list of applicable nodes will be empty.
    Nevertheless, in this case, it will be still possible to start them with |Supervisor|.

.. attention::

    As pointed out just before, |Supvisors| takes the information from the program configuration file. So this function
    will definitely NOT work if the program is unknown to the local |Supervisor|.

.. important:: *Convention for application names when using patterns and hashtags*

    When the hashtag is used for application ``addresses``, |Supvisors| cannot rely on the |Supervisor| configuration
    to map the application instances to the nodes.

    By convention, the application name MUST end with ``-N`` or ``_N``. The Nth application will be mapped to the Nth
    node of the list, i.e. the node at index ``N-1`` in the list.

    ``N`` must be striclty positive. Zero-padding is allowed, as long as ``N`` can be converted into an integer.


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
        <addresses>cliche01,cliche02,cliche03</addresses>
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


Node aliases
~~~~~~~~~~~~

When dealing with long lists of nodes, the content of application or program ``addresses`` options may impair
the readability of the rules file. It is possible to declare node aliases and to use the alias names in place
of the node names in the ``addresses`` option.

Here follows a few usage examples:

.. code-block:: xml

    <alias name="consoles">console01,console02,console03</alias>
    <alias name="servers">server01,server02</alias>

    <!-- working alias reference -->
    <alias name="all_ok">servers,consoles</alias>

    <model name="hci">
        <addresses>consoles</addresses>
    </model>

    <model name="service">
        <addresses>servers,consoles</addresses>
    </model>

.. hint:: *About aliases referencing other aliases*

    Based on the previous example, an alias referencing other aliases will only work if it is placed *before*
    the aliases referenced.

    At some point, the resulting node names are checked against the ``address_list``
    of the `rpcinterface extension point`_ so any unknown node name or remaining alias will simply be discarded.

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

        <!-- models -->
        <model name="disk_01">
            <addresses>cliche81</addresses>
            <expected_loading>5</expected_loading>
        </model>

        <model name="disk_02">
            <reference>disk_01</reference>
            <addresses>192.168.1.49</addresses>
        </model>

        <model name="disk_03">
            <reference>disk_01</reference>
            <addresses>cliche83</addresses>
        </model>

        <model name="converter">
            <addresses>*</addresses>
            <expected_loading>25</expected_loading>
        </model>

        <!-- complex test application -->
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

            <program pattern="mount_disk_">
                <addresses>#,192.168.1.49,cliche83,cliche84</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>2</stop_sequence>
                <required>true</required>
                <expected_loading>0</expected_loading>
            </program>

            <program name="copy_error">
                <addresses>cliche81</addresses>
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

            <program pattern="movie_server_">
                <addresses>#</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>1</stop_sequence>
                <expected_loading>5</expected_loading>
                <running_failure_strategy>CONTINUE</running_failure_strategy>
            </program>

            <program pattern="register_movies_">
                <addresses>#,cliche81,cliche83</addresses>
                <start_sequence>2</start_sequence>
                <wait_exit>true</wait_exit>
                <expected_loading>25</expected_loading>
            </program>

        </application>

        <!-- my_movies application -->
        <application name="my_movies">
            <start_sequence>4</start_sequence>
            <stop_sequence>2</stop_sequence>
            <starting_strategy>CONFIG</starting_strategy>
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
                <addresses>cliche84</addresses>
                <start_sequence>2</start_sequence>
                <required>true</required>
                <expected_loading>3</expected_loading>
            </program>

            <program name="hmi">
                <addresses>192.168.1.49,cliche81</addresses>
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
                <addresses>*</addresses>
            </program>

            <program name="converter_04">
                <reference>converter</reference>
                <addresses>cliche83,cliche81,192.168.1.49</addresses>
            </program>

            <program name="converter_07">
                <reference>converter</reference>
                <addresses>cliche81,cliche83,192.168.1.49</addresses>
            </program>

            <program pattern="converter_">
                <reference>converter</reference>
            </program>

         </application>

        <!-- player application -->
        <application name="player">
            <distributed>false</distributed>
            <addresses>cliche81,cliche83</addresses>
            <start_sequence>5</start_sequence>
            <starting_strategy>MOST_LOADED</starting_strategy>
            <starting_failure_strategy>ABORT</starting_failure_strategy>

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

        </application>

        <!-- web_movies application -->
        <application pattern="web_">
            <start_sequence>6</start_sequence>
            <stop_sequence>1</stop_sequence>
            <starting_strategy>LESS_LOADED</starting_strategy>

            <program name="web_browser">
                <addresses>*</addresses>
                <start_sequence>1</start_sequence>
                <expected_loading>4</expected_loading>
                <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
            </program>

        </application>

        <!-- disk_reader_81 application -->
        <application name="disk_reader_81">
            <start_sequence>1</start_sequence>
        </application>

    </root>

.. include:: common.rst
