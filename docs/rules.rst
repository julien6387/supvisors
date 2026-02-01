.. _rules_file:

|Supvisors| Rules File
======================

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
-----------------------

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

    The names are separated by commas and have to be taken from:

        * either the |Supvisors| identifiers declared in the ``supvisors_list`` option of the :ref:`configuration`,
        * and / or the |Supvisors| nicknames declared in the ``supvisors_list`` option,
        * and / or the declared `Instance aliases`_,
        * and / or a stereotype provided in the ``stereotypes`` option.

    Special values can be used. |br|
    The *wildcard symbol* ``*`` stands for all |Supvisors| instances. |br|
    Any list including a ``*`` is strictly equivalent to ``*`` alone.

    The *hashtag symbol* ``#`` can be used with a ``pattern`` definition and eventually complemented by a list
    of names, as defined above. |br|
    The aim is to assign the Nth |Supvisors| instance (in accordance with the sequence defined in the ``supvisors_list``
    option) or the Nth name of the subsequent list to the Nth instance of the application, **assuming that 'N'
    is provided at the end of the application name, preceded by a dash or an underscore**. |br|
    Examples will be given in `Application patterns`_.

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

        It is applied only when calling |Supvisors|' ``restart`` or ``shutdown`` XML-RPC.

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
-------------------

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

        * either the |Supvisors| identifiers declared in the ``supvisors_list`` option of the :ref:`configuration`,
        * and / or the |Supvisors| nicknames declared in the ``supvisors_list`` option,
        * and / or the declared `Instance aliases`_,
        * and / or a stereotype provided in the ``stereotypes`` option.

    Special values can be applied. |br|
    The *wildcard symbol* ``*`` stands for all |Supvisors| instances. |br|
    Any list including a ``*`` is strictly equivalent to ``*`` alone. |br|

    The *hashtag symbol* ``#`` and the *at symbol* ``@`` can be used with a ``pattern`` definition and eventually
    complemented by a list of |Supvisors| identifiers or nicknames. |br|
    The aim is to assign the Nth |Supvisors| instance (in accordance with the sequence defined in the ``supvisors_list``
    option) or the Nth name of the subsequent list to the Nth instance of the program in a homogeneous process group. |br|
    Examples will be given in `Program patterns`_.

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
--------------

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

Program patterns
~~~~~~~~~~~~~~~~

The *hashtag symbol* ``#`` and *at symbol* ``@`` in the program ``identifiers`` are designed for a program
that is meant to be started on every |Supvisors| instance available, or on a subset of them.

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

It is also possible to give a subset of |Supvisors| identifiers (or nicknames, aliases, stereotypes).

.. code-block:: xml

    <program pattern="prg_\d+">
        <identifiers>#,cliche04,cliche02</identifiers>
    </program>

|Supvisors| instances are chosen in accordance with the sequence given in ``supvisors_list`` or in the subsequent
list. In the second example above, :program:`prg_01` will be assigned to ``cliche04`` and :program:`prg_02` to
``cliche02``.

When using the |Supvisors| discovery mode is activated, the |Supvisors| instances are chosen in accordance with
their arrival in the system, which is random but fixed when established.

.. note::

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

As pointed out just before, |Supvisors| takes the information from the *local* program configuration.
This program is not necessarily known to all |Supervisor| instances, which is a relevant use case.
As written before, the |Supervisor| configuration may be different for all |Supvisors| instances,
including the definition of groups and programs.

During the handshake, |Supvisors| shares the context of all |Supvisors| instances, including the process index
deduced from the program configuration, so that the function may apply the logic described above to processes
locally unknown.

Application patterns
~~~~~~~~~~~~~~~~~~~~

Similarly, the *hashtag symbol* ``#`` can be used in the application ``identifiers``, with a few constraints.

.. note::

    The *at symbol* ``@`` is not yet implemented for the application ``identifiers``.

When the hashtag is used for the application ``identifiers``, |Supvisors| cannot rely on the |Supervisor|
configuration to map the application instances to the |Supvisors| instances, because there is no principle
of "homogeneous groups of groups".

By convention, the application name MUST end with ``-N`` or ``_N``. The Nth application will be mapped to the Nth
|Supvisors| instance, rolling over the list if necessary.

.. important::

    **``N`` must be strictly positive.** |br|
    Zero-padding is allowed, as long as ``N`` can be converted into an integer.

As an example, based on the following simplified |Supervisor| configuration:

.. code-block:: ini

    [group:app-1]
    programs=any_program_list

    [group:app-02]
    programs=any_program_list

    [group:app-3]
    programs=any_program_list

And the following simplified |Supvisors| rules:

.. code-block:: xml

    <application pattern="app-">
        <distribution>SINGLE_INSTANCE</distribution>
        <identifiers>#,cliche04,cliche02</identifiers>
    </application>

In the example above:

    * all the processes of :program:`app-1` will be assigned to the |Supvisors| instance referred as ``cliche04``,
    * all the processes of :program:`app-02` will be assigned to the |Supvisors| instance referred as ``cliche02``,
    * all the processes of :program:`app-3` will be assigned to the |Supvisors| instance referred as ``cliche04``.


``<model>`` rules
-----------------

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
----------------

When dealing with long lists of |Supvisors| instances, the content of application or program ``identifiers`` options
may impair the readability of the rules file. It is possible to declare instance aliases and to use the alias names
in place of the |Supvisors| identifiers or nicknames in the ``identifiers`` option.

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

    At some point, the resulting names are checked against the |Supvisors| identifiers and nicknames so any unknown name
    or remaining alias will simply be discarded.

.. code-block:: xml

    <!-- Correct alias reference -->
    <alias name="all_ok">servers,consoles</alias>

    <alias name="consoles">console01,console02,console03</alias>
    <alias name="servers">server01,server02</alias>

    <!-- Wrong alias reference -->
    <alias name="all_ko">servers,consoles</alias>


Rules File Example
------------------

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
