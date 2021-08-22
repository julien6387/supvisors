.. _scenario_1:

Scenario 1
==========

Context
-------

In this use case, the application is distributed over 3 nodes. The process distribution is fixed.
The application logs and other data are written to a disk that is made available through a NFS mount point.


Requirements
------------

Here are the use case requirements:

Requirement 1
    |Req 1|

Requirement 2
    |Req 2|

Requirement 3
    |Req 3|

Requirement 4
    |Req 4|

Requirement 5
    |Req 5|

Requirement 6
    |Req 6|

Requirement 7
    |Req 7|

.. |Req 1| replace:: Due to the inter-processes communication scheme, the process distribution shall be fixed.
.. |Req 1 abbr| replace:: :abbr:`Requirement 1 (Due to the inter-processes communication scheme, the process distribution shall be fixed.)`
.. |Req 2| replace:: The application shall wait for the NFS mount point before it is started.
.. |Req 2 abbr| replace:: :abbr:`Requirement 2 (The application shall wait for the NFS mount point before it is started.)`
.. |Req 3| replace:: An operational status of the application shall be provided.
.. |Req 3 abbr| replace:: :abbr:`Requirement 3 (An operational status of the application shall be provided.)`
.. |Req 4| replace:: The user shall not be able to start an unexpected application process on any other node.
.. |Req 4 abbr| replace:: :abbr:`Requirement 4 (The user shall not be able to start an unexpected application process on any other node.)`
.. |Req 5| replace:: The application shall be restarted on the 3 nodes upon user request.
.. |Req 5 abbr| replace:: :abbr:`Requirement 5 (The application shall be restarted on the 3 nodes upon user request.)`
.. |Req 6| replace:: There shall be a non-distributed configuration for developers' use, assuming a different inter-processes communication scheme.
.. |Req 6 abbr| replace:: :abbr:`Requirement 6 (There shall be a non-distributed configuration for developers' use, assuming a different inter-processes communication scheme.)`
.. |Req 7| replace:: The non-distributed configuration shall not wait for the NFS mount point.
.. |Req 7 abbr| replace:: :abbr:`Requirement 7 (The non-distributed configuration shall not wait for the NFS mount point.)`


|Supervisor| configuration
--------------------------

There are undoubtedly many ways to skin the cat. Here follows one solution.

As an answer to |Req 1 abbr| and |Req 7 abbr|, let's split the |Supervisor| configuration file into 4 parts:

    * the ``supervisord.conf`` configuration file ;
    * the program definitions and the group definition (``.ini`` files) for the first node ;
    * the program definitions and the group definition (``.ini`` files) for the second node ;
    * the program definitions and the group definition (``.ini`` files) for the third node.

All program are configured using ``autostart=true``.

For packaging facility, the full configuration is available to all nodes but the ``include`` section of the
configuration file uses the ``host_node_name`` so that the running configuration is actually different on all nodes.

.. code-block:: ini

    [include]
    files = %(host_node_name)s/*.ini

The resulting file tree would be as follows.

.. code-block:: bash

    [bash] > tree
    .
    ├── etc
    │         ├── cliche81
    │         │         ├── group_cliche81.ini
    │         │         └── programs_cliche81.ini
    │         ├── cliche82
    │         │         ├── group_cliche82.ini
    │         │         └── programs_cliche82.ini
    │         ├── cliche83
    │         │         ├── group_cliche83.ini
    │         │         └── programs_cliche83.ini
    │         └── supervisord.conf


For |Req 6 abbr|, let's just define a group where all programs are declared.
The proposal is to have 2 |Supervisor| configuration files, one for the distributed application and the other
for the non-distributed application, the variation being just in the include section.

About |Req 2 abbr|, |Supervisor| does not provide any facility to stage the starting sequence (refer to
`Issue #122 - supervisord Starts All Processes at the Same Time <https://github.com/Supervisor/supervisor/issues/122>`_).
A workaround here would be to insert a wait loop in all the application programs (in the program command line
or in the program source code). The idea of pushing this wait loop outside the |Supervisor| scope - just before
starting :program:`supervisord` - is excluded as it would impose this dependency on other applications eventually managed
by |Supervisor|.

With regard to |Req 7 abbr|, this workaround would require different program commands or parameters, so finally
different program definitions from |Supervisor| configuration perspective.

.. code-block:: bash

    [bash] > tree
    .
    ├── etc
    │         ├── cliche81
    │         │         ├── group_cliche81.ini
    │         │         └── programs_cliche81.ini
    │         ├── cliche82
    │         │         ├── group_cliche82.ini
    │         │         └── programs_cliche82.ini
    │         ├── cliche83
    │         │         ├── group_cliche83.ini
    │         │         └── programs_cliche83.ini
    │         ├── localhost
    │         │         ├── group_localhost.ini
    │         │         └── programs_localhost.ini
    │         ├── supervisord.conf -> supervisord_distributed.conf
    │         ├── supervisord_distributed.conf
    │         ├── supervisord_localhost.conf
    │         └── supvisors-rules.xml

Here is the resulting ``include`` sections:

.. code-block:: ini

    # include section for distributed application in supervisord_distributed.conf
    [include]
    files = %(host_node_name)s/*.ini

    # include section for non-distributed application in supervisord_localhost.conf
    [include]
    files = localhost/*.ini

|Supervisor| provides nothing for |Req 3 abbr|. The user has to evaluate the operational status based on the process
status provided by the |Supervisor| instances on the 3 nodes, either using multiple :program:`supervisorctl` shell
commands, XML-RPCs or event listeners.

To restart the whole application (|Req 5 abbr|), the user can perform :program:`supervisorctl` shell commands
or XML-RPCs on each |Supervisor| instance.

.. code-block:: bash

    [bash] > for i in cliche81 cliche82 cliche83
    ... do
    ...    supervisorctl -s http://$i:<port> restart <group>:*
    ... done

Eventually, all the requirements could be met using |Supervisor| but it would require additional development
at application level to build an operational status, based on process information provided by |Supervisor|.

It would also require some additional complexity in the configuration files and in the program command lines
to manage a staged starting sequence of the programs in the group and to manage the distribution of the application
over different platforms.


Involving |Supvisors|
---------------------

A solution based on |Supvisors| could use the following |Supervisor| configuration (same principles as the previous
section):

    * the ``supervisord_distributed.conf`` configuration file for the distributed application ;
    * the ``supervisord_localhost.conf`` configuration file for the non-distributed application ;
    * the program definitions and the group definition (``.ini`` files) for the first node ;
    * the program definitions and the group definition (``.ini`` files) for the second node ;
    * the program definitions and the group definition (``.ini`` files) for the third node ;
    * the group definition including all application programs for a local node.

All programs are now configured using ``autostart=false``.

Introducing the staged start sequence
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

About |Req 2 abbr|, |Supvisors| manages staged starting sequences and it offers a possibility to wait for a
planned exit of a process in the sequence.
So let's define a new program ``wait_nfs_mount_X`` per node and whose role is to exit (using an expected exit code,
as defined in `Supervisor program configuration <http://supervisord.org/configuration.html#program-x-section-values>`_)
as soon as the NFS mount is available.

Complying about |Req 7 abbr| is just about avoiding the inclusion of the ``wait_nfs_mount_X`` programs in the
|Supervisor| configuration file in the case of a non-distributed application. That's why the |Supervisor|
configuration of these programs is isolated from the configuration of the other programs.
That way, |Supvisors| makes it possible to avoid an impact to program definitions, scripts and source code
when dealing with such a requirement.

Here follows what the include section may look like in both |Supervisor| configuration files.

.. code-block:: ini

    # include section for distributed application in supervisord_distributed.conf (unchanged)
    [include]
    files = %(host_node_name)s/*.ini

    # include section for non-distributed application in supervisord_localhost.conf
    # the same program definitions as the distributed application are used
    [include]
    files = */programs_*.ini localhost/group_localhost.ini

Rules file
~~~~~~~~~~

Now that programs are not started automatically by |Supervisor|, a |Supvisors| rules file is needed to define
the staged starting sequence. A first naive - yet functional - approach would be to use a model for all programs
to be started on the same node.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <!-- models -->
        <model name="model_cliche81">
            <addresses>cliche81</addresses>
            <start_sequence>2</start_sequence>
            <required>true</required>
        </model>
        <model name="model_cliche82">
            <reference>model_cliche81</reference>
            <addresses>cliche82</addresses>
        </model>
        <model name="model_cliche83">
            <reference>model_cliche81</reference>
            <addresses>cliche83</addresses>
        </model>
        <!-- Scenario 1 Application -->
        <application name="scenario_1">
            <start_sequence>1</start_sequence>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <!-- Programs on cliche81 -->
            <program name="hci">
                <reference>model_cliche81</reference>
            </program>
            <program name="config_manager">
                <reference>model_cliche81</reference>
            </program>
            <program name="data_processing">
                <reference>model_cliche81</reference>
            </program>
            <program name="external_interface">
                <reference>model_cliche81</reference>
            </program>
            <program name="data_recorder">
                <reference>model_cliche81</reference>
            </program>
            <program name="wait_nfs_mount_1">
                <reference>model_cliche81</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
            <!-- Programs on cliche82 -->
            <program name="sensor_acquisition_1">
                <reference>model_cliche82</reference>
            </program>
            <program name="sensor_processing_1">
                <reference>model_cliche82</reference>
            </program>
            <program name="wait_nfs_mount_2">
                <reference>model_cliche82</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
            <!-- Programs on cliche83 -->
            <program name="sensor_acquisition_2">
                <reference>model_cliche83</reference>
            </program>
            <program name="sensor_processing_2">
                <reference>model_cliche83</reference>
            </program>
            <program name="wait_nfs_mount_3">
                <reference>model_cliche83</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
        </application>
    </root>

.. note::

    A few words about how the ``wait_nfs_mount_X`` programs have been introduced here. It has to be noted that:

        * the ``start_sequence`` of these programs is lower than the ``start_sequence`` of the other application programs ;
        * their attribute ``wait_exit`` is set to ``true``.

    The consequence is that the 3 programs ``wait_nfs_mount_X`` are started first on their respective node
    when starting the :program:`scenario_1` application. Then |Supvisors| waits for *all* of them to exit before it triggers
    the starting of the other programs.

Well, assuming that the node name could be included as a prefix to the program names, that would simplify
the rules file a bit.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <!-- models -->
        <model name="model_cliche81">
            <addresses>cliche81</addresses>
            <start_sequence>2</start_sequence>
            <required>true</required>
        </model>
        <model name="model_cliche82">
            <reference>model_cliche81</reference>
            <addresses>cliche82</addresses>
        </model>
        <model name="model_cliche83">
            <reference>model_cliche81</reference>
            <addresses>cliche83</addresses>
        </model>
        <!-- Scenario 1 Application -->
        <application name="scenario_1">
            <start_sequence>1</start_sequence>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <!-- Programs on cliche81 -->
            <program pattern="cliche81_">
                <reference>model_cliche81</reference>
            </program>
            <program name="wait_nfs_mount_1">
                <reference>model_cliche81</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
            <!-- Programs on cliche82 -->
            <program pattern="cliche82_">
                <reference>model_cliche82</reference>
            </program>
            <program name="wait_nfs_mount_2">
                <reference>model_cliche82</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
            <!-- Programs on cliche83 -->
            <program pattern="cliche83_">
                <reference>model_cliche83</reference>
            </program>
            <program name="wait_nfs_mount_3">
                <reference>model_cliche83</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
        </application>
    </root>

A bit shorter, still functional but the program names are now quite ugly. And the non-distributed version has not been
considered yet. With this approach, a different rules file is required to replace the node names with the developer's
host name - assumed called ``cliche81`` here for the example.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <!-- Scenario 1 Application -->
        <application name="scenario_1">
            <start_sequence>1</start_sequence>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <!-- Programs on localhost -->
            <program pattern="">
                <addresses>cliche81</addresses>
                <start_sequence>1</start_sequence>
                <required>true</required>
            </program>
        </application>
    </root>

This rules file is very simple here as all programs have the exactly same rules.

.. hint::

    When the same rules apply to all programs in an application, an empty pattern can be used as it will match
    all program names of the application.

But actually, there is a much more simple solution in the present case. Let's consider this instead:

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <!-- models -->
        <model name="model_scenario_1">
            <start_sequence>2</start_sequence>
            <required>true</required>
        </model>
        <!-- Scenario 1 Application -->
        <application name="scenario_1">
            <start_sequence>1</start_sequence>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <program pattern="">
                <reference>model_scenario_1</reference>
            </program>
            <program pattern="wait_nfs_mount">
                <reference>model_scenario_1</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
        </application>
    </root>

Much shorter. Yet it does the same. For both the distributed application and the non-distributed application !

The main point is that the ``addresses`` attribute is not used at all. Clearly, this gives |Supvisors|
the authorization to start all programs on every nodes. However |Supvisors| knows about the |Supervisor| configuration
in the 3 nodes. When choosing a node to start a program, |Supvisors| considers the intersection between the authorized
nodes - all of them here - and the possible nodes, i.e. the active nodes where the program is defined in |Supervisor|.
One of the first decisions in this use case is that every programs are known to only one |Supervisor| instance so that
gives |Supvisors| only one possibility.

For |Req 3 abbr|, |Supvisors| provides the operational status of the application based on the status of its
processes, in accordance with their importance. In the present example, all programs are defined with the same
importance (``required`` set to ``true``).

The key point here is that |Supvisors| is able to build a single application from the processes configured
on the 3 nodes because the same group name (:program:`scenario_1`) is used in all |Supervisor| configuration files.

Here follows the relevant sections of the ``supervisord_distributed.conf`` configuration file, including the declaration
of the |Supvisors| plugin.

.. code-block:: ini

    [include]
    files = %(host_node_name)s/*.ini

    [supvisors]
    address_list=cliche81,cliche82,cliche83
    rules_file=etc/supvisors_rules.xml

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin

And the equivalent in the ``supervisord_localhost.conf`` configuration file. No ``address_list`` is provided here as
the default value is the local host name, which is perfectly suitable here.

.. code-block:: ini

    [include]
    files = */programs_*.ini localhost/group_localhost.ini

    [supvisors]
    rules_file=etc/supvisors_rules.xml

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

    [ctlplugin:supvisors]
    supervisor.ctl_factory = supvisors.supvisorsctl:make_supvisors_controller_plugin

The final file tree is as follows.

.. code-block:: bash

    [bash] > tree
    .
    ├── etc
    │         ├── cliche81
    │         │         ├── group_cliche81.ini
    │         │         ├── programs_cliche81.ini
    │         │         └── wait_nfs_mount.ini
    │         ├── cliche82
    │         │         ├── group_cliche82.ini
    │         │         ├── programs_cliche82.ini
    │         │         └── wait_nfs_mount.ini
    │         ├── cliche83
    │         │         ├── group_cliche83.ini
    │         │         ├── programs_cliche83.ini
    │         │         └── wait_nfs_mount.ini
    │         ├── localhost
    │         │         └── group_localhost.ini
    │         ├── supervisord.conf -> supervisord_distributed.conf
    │         ├── supervisord_distributed.conf
    │         ├── supervisord_localhost.conf
    │         └── supvisors_rules.xml


Control & Status
~~~~~~~~~~~~~~~~

The operational status of Scenario 1 required by the |Req 3 abbr| is made available through:

    * the :ref:`dashboard_application` of the |Supvisors| Web UI, as a LED near the application state,
    * the :ref:`xml_rpc` (example below),
    * the extended :program:`supervisorctl` :ref:`extended_status` (example below),
    * the :ref:`event_interface`.

>>> from supvisors.rpcrequests import getRPCInterface
>>> proxy = getRPCInterface('localhost', {'SUPERVISOR_SERVER_URL': 'http://:61000'})
>>> proxy.supvisors.get_application_info('scenario_1')
{'application_name': 'scenario_1', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False}

.. code-block:: bash

    [bash] > supervisorctl -c etc/supervisord_localhost.conf application_info scenario_1
    Node         State     Major  Minor
    scenario_1   RUNNING   True   False

To restart the whole application (|Req 5 abbr|), the following is available:

    * the :ref:`xml_rpc` (example below),
    * the extended :program:`supervisorctl` :ref:`application_control` (example below),
    * the restart button |restart| at the top right of the :ref:`dashboard_application` of the  |Supvisors| Web UI.

>>> from supvisors.rpcrequests import getRPCInterface
>>> proxy = getRPCInterface('localhost', {'SUPERVISOR_SERVER_URL': 'http://:61000'})
>>> proxy.supvisors.restart_application('CONFIG', 'scenario_1')
True

.. code-block:: bash

    [bash] > supervisorctl -c etc/supervisord_localhost.conf restart_application CONFIG scenario_1
    scenario_1 restarted

Here is a snapshot of the Application page of the |Supvisors| Web UI for the Scenario 1 application.

.. image:: images/supvisors_scenario_1.png
    :alt: Supvisors Use Cases - Scenario 1
    :align: center

As a conclusion, all the requirements are met using |Supvisors| and without any impact on the application to be
supervised. |Supvisors| brings gain over application control and status.


Example
-------

The full example is available in `Supvisors Use Cases - Scenario 1 <https://github.com/julien6387/supvisors/tree/master/supvisors/test/use_cases/scenario_1>`_.

.. include:: common.rst
