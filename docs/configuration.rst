.. _configuration:

Configuration
=============

Supervisor's Configuration File
-------------------------------

This section explains how **Supvisors** uses and complements the
`Supervisor configuration <http://supervisord.org/configuration.html>`_.


Extension points
~~~~~~~~~~~~~~~~

**Supvisors** extends the `Supervisor's XML-RPC API <http://supervisord.org/xmlrpc.html>`_.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.rpcinterface:make_supvisors_rpcinterface

**Supvisors** extends also `supervisorctl <http://supervisord.org/running.html#running-supervisorctl>`_.
This possibility is not documented in Supervisor.

.. code-block:: ini

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin


.. _supvisors_section:

``[supvisors]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The parameters of **Supvisors** are set through an additional section ``[supvisors]`` in the Supervisor configuration file.

``address_list``

    The list of host names or IP addresses where **Supvisors** will be running, separated by commas.

    *Default*:  None.

    *Required*:  Yes.

``deployment_file``

    The absolute or relative path of the XML rules file. The contents of this file is described in `Supvisors' Rules File`_.

    *Default*:  None.

    *Required*:  No.

``auto_fence``

    When true, **Supvisors** won't try to reconnect to a **Supvisors** instance that has been inactive.
    This functionality is detailed in :ref:`auto_fencing`.

    *Default*:  false.

    *Required*:  No.

``internal_port``

    The internal port number used to publish local events to remote **Supvisors** instances.
    Events are published through a PyZMQ TCP socket.

    *Default*:  65001.

    *Required*:  No.


``event_port``

    The port number used to publish all **Supvisors** events (Address, Application and Process events).
    Events are published through a PyZMQ TCP socket. The protocol of this interface is explained in :ref:`event_interface`.

    *Default*:  65002.

    *Required*:  No.

``synchro_timeout``

    The time in seconds that **Supvisors** waits for all expected **Supvisors** instances to publish.
    This use of this option is detailed in :ref:`synchronizing`.

    *Default*:  15.

    *Required*:  No.

``deployment_strategy``

    The strategy used to start applications on addresses.
    Possible values are in { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.
    The use of this option is detailed in :ref:`starting_strategy`.

    *Default*:  ``CONFIG``.

    *Required*:  No.

``conciliation_strategy``

    The strategy used to solve conflicts upon detection that multiple instances of the same program are running.
    Possible values are in { ``SENICIDE``, ``INFANTICIDE``, ``USER``, ``STOP``, ``RESTART`` }.
    The use of this option is detailed in :ref:`conciliation`.

    *Default*:  ``USER``.

    *Required*:  No.

``stats_periods``

    The list of periods for which the statistics will be provided in the **Supvisors** :ref:`dashboard`, separated by commas.
    Up to 3 values are allowed in [5 ; 3600] seconds, each of them MUST be a multiple of 5.

    *Default*:  10.

    *Required*:  No.

``stats_histo``

    The depth of the statistics history. Value in [10 ; 1500].

    *Default*:  200.

    *Required*:  No.

The logging options are strictly identical to Supervisor's. By the way, it is the same logger that is used.
These options are more detailed in
`supervisord Section values <http://supervisord.org/configuration.html#supervisord-section-values>`_.

``logfile``

    The absolute or relative path of the **Supvisors** log file.

    *Default*:  :file:`supvisors.log`.

    *Required*:  No.
    
``logfile_maxbytes``

    The maximum size of the **Supvisors** log file.

    *Default*:  50MB.

    *Required*:  No.

``logfile_backups``

    The number of **Supvisors** backup log files.

    *Default*:  10.

    *Required*:  No.

``loglevel``

    The logging level.

    *Default*:  info.

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
    deployment_file=./etc/my_movies.xml
    auto_fence=false
    internal_port=60001
    event_port=60002
    synchro_timeout=20
    deployment_strategy=LESS_LOADED
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

This part describes the contents of the XML rules file declared in the ``deployment_file`` option.

Basically, the rules file contains rules that define how applications and programs should be started.
It relies on the Supervisor group and program definitions.
The rules define the quality of service expected and how the programs are meant to be started and sto.


If the `lxml <http://lxml.de>`_ package is available on the system, **Supvisors** uses it to validate
the XML rules file before it is used.

.. hint::

    It is still possbile to validate the XML rules file manually.
    The XSD contents used to validate the XML can be found in the module ``supvisors.parser``.
    Once extracted to a file (here :file:`rules.xsd`), just use :command:`xmllint` to validate:

    .. code-block:: bash

        [bash] > xmllint --noout --schema rules.xsd user_rules.xml


``program`` Rules
~~~~~~~~~~~~~~~~~

The ``program`` rules must be included in ``application`` rules.
Here follows the definition of the rules applicable to a program.

``name``

    This attribute gives the name of the program. A Supervisor program name is expected.

    *Default*:  None.

    *Required*:  Yes.

``reference``

    This element gives the name of the applicable ``model``, defined in `model Rules`_.
    This use of the ``reference`` element is exclusive to the use of the following elements.

    *Default*:  None.

    *Required*:  Only if none of the following elements is used.

``addresses``

    This element gives the list of host names or IP addresses. Applicable values are:

        * a subset of the ``address_list`` defined in `[supvisors] Section Values`_,
        * ``*``: stands for all values in ``address_list``.
        * ``#``: stands for the address in ``address_list`` having the same index as the program in a homogeneous group. This will be detailed in the `Pattern Rules`_.

    *Default*:  ``*``.

    *Required*:  No.

``required``

    This element gives the importance of the program for the application.
    If true (resp. false), a failure of the program is considered major (resp. minor).
    This is quite informative and is mainly used to give the operational status of the application.
        
    *Default*:  false.

    *Required*:  No.

``start_sequence``

    This element gives the starting rank of the program when the application is starting.
    When <= 0, the program is not automatically started.
    When > 0, the program is started automatically in the given order.
        
    *Default*:  0.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the program when the application is stopping.
    When <= 0, the program is stopped immediately if running.
    When > 0, the program is stopped in the given order.
        
    *Default*:  0.

    *Required*:  No.

``wait_exit``

    If the value of this element is set to true, Supvisors waits for the process to exit
    before deploying the next sequence. This may be useful for scripts used to load a database,
    to mount disks, to prepare the application working directory, etc.
        
    *Default*:  false.

    *Required*:  No.

``loading``

    This element gives the expected percent usage of resources. The value is a estimation and the meaning
    in terms of resources (CPU, memory, network) is in the user's hands.
    
    This can be used in **Supvisors** to ensure that a system is not overloaded with greedy processes.
    When multiple addresses are available, the `` loading`` value helps to distribute processes over
    the systems available, so that the system remains safe.

    .. note:: *About the choice of a user estimation.*

        Although **Supvisors** is taking measurements on each system where it is running, it has
        been chosen not to use these figures for the loading purpose. Indeed, the resources consumption
        of a process may be very variable in time and is not foreseeable.

        It is recommended to give a value based on a average usage of the resources in worst case
        configuration and to add a margin corresponding to the standard deviation.

    *Default*:  1.

    *Required*:  No.

``running_failure_strategy``

    **Not implemented yet**
    
    This element gives the strategy applied when the required process is unexpectanly stopped in a running application.
    Possible values are:

        * ``CONTINUE``: Skip the failure. The application stays with the major failure.
        * ``STOP``: Stop the application.
        * ``RESTART``: Restart the application.

    *Default*:  ``CONTINUE``.

    *Required*:  No.

.. code-block:: xml

    <program name="prg_00">
        <addresses>10.0.0.1 10.0.0.3 system02</addresses>
        <required>true</required>
        <start_sequence>1</start_sequence>
        <stop_sequence>1</stop_sequence>
        <wait_exit>false</wait_exit>
        <loading>3</loading>
    </program>


``pattern`` Rules
~~~~~~~~~~~~~~~~~

It may be quite tedious to give these informations to each program, especially if multiple programs use common rules.
So two mechanisms were put in place to help.

The first is the ``pattern``. It can be used to configure a set of programs in a more flexible way than just
considering homogeneous programs, like Supervisor does.

Like the ``program`` element, the ``pattern`` must be included in ``application`` rules. The same options are applicable.
The difference is in the ``name`` usage. For a pattern definition, a substring of any Supervisor program name is expected.

.. code-block:: xml

    <pattern name="prg_">
        <addresses>10.0.0.1 10.0.0.3 system02</addresses>
        <start_sequence>2</start_sequence>
        <required>true</required>
    </pattern>

.. attention:: *About the pattern names*.

    Precautions must be taken when using a ``pattern`` definition.
    In the previous example, the rules are applicable to every program names containing the ``"prg_"`` substring,
    so that it matches ``prg_00``, ``prg_dummy``, but also ``dummy_prg_2``.

    As a general rule, when considering a program name, **Supvisors** applies a ``program`` definition, if found,
    before trying to associate a ``pattern`` definition.

    It also may happen that several patterns match the same program name. In this case, **Supvisors** chooses the pattern
    with the greatest matching, or arbitrarily the first of them if such a rule does not discrimate enough. So given two pattern
    names ``prg`` and ``prg_``, **Supvisors** applies the rules associated to ``prg_`` when consirering the program
    ``prg_00``.

.. note:: *About the use of ``#`` in ``addresses``.*

    The intention is for a program that is meant to be started on each address in the address list.
    As an example, consider an extract of the following Supervisor configuration:

    .. code-block:: ini

        [supvisors]
        address_list=10.0.0.1,10.0.0.2,10.0.0.3,10.0.0.4,10.0.0.5

        [program:prg]
        process_name=prg_%(process_num)02d
        numprocs=5

    Without this option, it would be necessary to have one program definition for each instance.

    .. code-block:: xml

        <program name="prg_00">
            <addresses>10.0.0.1</addresses>
        </program>

        <!-- definitions for prg_01, prg_02, prg_03 -->
 
        <program name="prg_04">
            <addresses>10.0.0.5</addresses>
        </program>

    Now with this option, the program definition is more simple.

    .. code-block:: xml

        <pattern name="prg_">
            <addresses>#</addresses>
        </pattern>

.. attention::

    Addresses are chosen in accordance with the sequence given in ``address_list``.
    In the example above, if the two first addresses are swapped, ``prg_00`` will be addressed to ``10.0.0.2`` and ``prg_01`` to ``10.0.0.1``.

.. attention::

    In the program configuration file, it is expected that the ``numprocs`` value matches the number of elements in ``address_list``.
    If the length of ``address_list`` is greater than the ``numprocs`` value, programs will be addressed to the ``numprocs`` first addresses.
    On the other side, if the length of ``address_list`` is lower than the ``numprocs`` value,
    the last programs won't be addressed to any address and it won't be possible to start them using **Supvisors**.
    Nevertheless, in this case, it will be still possible to start them with Supervisor.


``model`` Rules
~~~~~~~~~~~~~~~

The second mechanism is the ``model`` definition.
The ``program`` definition is extended to a generic model, that can be defined outside the application scope,
so that the same definition can be applied to multiple programs, in any application.

The same options are applicable, **excepting** the ``reference`` option, which doesn't make sense here.
There is no particular expectation for the name attribute of a ``model``.

Here follows an example of model:

.. code-block:: xml

    <model name="X11_model">
	    <addresses>192.168.0.10 192.168.0.12 sample03</addresses>
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
    </pattern>


``application`` Rules
~~~~~~~~~~~~~~~~~~~~~

Here follows the definition of the rules applicable to an application.

``name``

    This attribute gives the name of the application. A Supervisor group name is expected.

    *Default*:  None.

    *Required*:  Yes.

``start_sequence``

    This element gives the starting rank of the application in the ``DEPLOYMENT`` state, when applications are started automatically.
    When <= 0, the application is not started.
    When > 0, the application is started in the given order.

    *Default*:  0.

    *Required*:  No.

``stop_sequence``

    This element gives the stopping rank of the application when all applications are stopped just before **Supvisors** is restarted or shut down.
    When <= 0, **Supvisors** does nothing and let Supervisor do the job, i.e. stop everything in any order.
    When > 0, **Supvisors** stops the application in the given order BEFORE the restart or shutdown of Supervisor is requested.

    *Default*:  0.

    *Required*:  No.

    .. attention::
    
        The ``stop_sequence`` is **not** taken into account:
        
            * when calling Supervisor's ``restart`` or ``shutdown`` XML-RPC,
            * when stopping the :command:`supervisord` daemon.

        It only works when calling **Supvisor**'s ``restart`` or ``shutdown``.

``starting_failure_strategy``

    **Not implemented yet**
    
    This element gives the strategy applied upon a major failure in the starting phase of an application.
    Possible values are:

        * ``ABORT``: Abort the application starting.
        * ``STOP``: Stop the application.
        * ``CONTINUE``: Skip the failure and continue the application starting.

    *Default*:  ABORT.

    *Required*:  No.

``program``

    This element defines the program rules that are applicable to the unique program whose name correspond to the name attribute of the ``program`` element.
    Obviously, the definition of an application can include multiple ``program`` elements.

    *Default*:  None.

    *Required*:  No.

``pattern``

    This element defines the program rules that are applicable to all programs whose name matches the name attribute of the ``pattern`` element.
    Obviously, the definition of an application can include multiple ``program`` elements.

    *Default*:  None.

    *Required*:  No.


Rules File Example
~~~~~~~~~~~~~~~~~~

Here follows a complete example of rules files. It is used in **Supvisors** tests.

.. code-block:: xml

    ?xml version="1.0" encoding="UTF-8" standalone="no"?>
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

        <!-- movies_database application -->
        <application name="database">
            <start_sequence>2</start_sequence>
            <stop_sequence>3</stop_sequence>

            <pattern name="movie_server_">
                <addresses>#</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>1</stop_sequence>
                <expected_loading>5</expected_loading>
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
            <start_sequence>3</start_sequence>
            <stop_sequence>2</stop_sequence>

            <program name="manager">
                <addresses>*</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>2</stop_sequence>
                <required>true</required>
                <expected_loading>5</expected_loading>
            </program>

            <program name="hmi">
                <!-- no screen on cliche03 -->
                <addresses>cliche02 cliche01</addresses>
                <start_sequence>2</start_sequence>
                <stop_sequence>1</stop_sequence>
                <required>true</required>
                <expected_loading>10</expected_loading>
            </program>

            <program name="disk_01_">
                <reference>disk_01</reference>
            </program>

            <program name="disk_02_">
                <reference>disk_02</reference>
            </program>

            <program name="disk_03_">
                <reference>disk_03</reference>
            </program>

            <pattern name="error_disk_">
                <reference>disk_error</reference>
            </pattern>

            <pattern name="converter_">
                <expected_loading>25</expected_loading>
            </pattern>

         </application>

        <!-- web_movies application -->
        <application name="web_movies">
            <start_sequence>4</start_sequence>
            <stop_sequence>1</stop_sequence>

            <program name="web_server">
                <addresses>*</addresses>
                <start_sequence>1</start_sequence>
                <stop_sequence>1</stop_sequence>
                <required>true</required>
                <expected_loading>3</expected_loading>
            </program>

            <program name="web_browser">
                <addresses>*</addresses>
                <start_sequence>2</start_sequence>
                <expected_loading>4</expected_loading>
            </program>

        </application>

    </root>

