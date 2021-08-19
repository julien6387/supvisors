.. _scenario_2:

Scenario 2
==========

Context
-------

In this use case, the application "Scenario2" is used to control an item.
It is delivered in 2 parts:

    * ``scen2_srv``: dedicated to services and designed to run on a server only,
    * ``scen2_hci``: dedicated to Human Computer Interfaces (HCI) and designed to run on a console only.

``scen2_hci`` is started on demand from a console, whereas ``scen2_srv`` is available on startup.
``scen2_srv`` cannot be distributed because of its inter-processes communication scheme.
``scen2_hci`` is not distributed so that the user gets all the windows on the same screen.
An internal data bus will allow ``scen2_hci`` to communicate with ``scen2_srv``.

Multiple instances of the "Scenario2" application can be started because there are multiple items to control.

A common data bus - out of this application's scope - is available to exchange data between "Scenario2" instances
and other applications dealing with other types of items and/or a higher control/command application.


Requirements
------------

Here follows the use case requirements.

Global requirements:
~~~~~~~~~~~~~~~~~~~~

    1. ``scen2_hci`` and ``scen2_srv`` shall not be distributed.
    2. Given X items to control, it shall be possible to start X instances of the application.
    3. An operational status of each application shall be provided.
    4. ``scen2_hci`` and ``scen2_srv`` shall start only when their internal data bus is operational.
    5. The number of application instances running shall be limited in accordance with the resources available (consoles or servers up).

Services part:
~~~~~~~~~~~~~~

    10. ``scen2_srv`` shall be started on a server only.
    11. ``scen2_srv`` shall be automatically started.
    12. There shall be a load-balancing strategy to distribute the X instances of ``scen2_srv`` over the servers.
    13. Upon failure in its starting sequence, ``scen2_srv`` shall be stopped so that it doesn't consume resources uselessly.
    14. As ``scen2_srv`` is highly dependent from the internal data bus, ``scen2_srv`` shall be fully restarted if the internal data bus crashes.
    15. Upon server failure, the ``scen2_srv`` instance shall be restarted on another server, in accordance with the load-balancing strategy.
    16. The ``scen2_srv`` interface with the common data bus shall start only when the common data bus is operational.

HCI part:
~~~~~~~~~

    20. ``scen2_hci`` shall be started upon user request.
    21. ``scen2_hci`` shall be started on the console from where the user request has been done.
    22. When starting ``scen2_hci``, the user shall choose the item to control.
    23. The user shall not be able to start twice a ``scen2_hci`` that controls the same item.
    24. Upon failure, the starting sequence of ``scen2_hci`` shall continue so that the user is made aware of.
    25. As ``scen2_hci`` is highly dependent from the internal data bus, ``scen2_hci`` shall be fully stopped if the internal data bus crashes.
    26. Upon console failure, ``scen2_hci`` shall not be restarted on another console.
    27. ``scen2_hci`` shall be stopped upon user request.



Supervisor configuration
------------------------

As an answer to **Requirement 1** and **Requirement 4**, let's split the Supervisor configuration file into 4 parts:

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


For **Requirement 6**, let's just define a group where all programs are declared.
The proposal is to have 2 *Supervisor* configuration files, one for the distributed application and the other
for the non-distributed application, the variation being just in the include section.

About **Requirement 2**, *Supervisor* does not provide any facility to stage the starting sequence (refer to
`Issue #122 - supervisord Starts All Processes at the Same Time <https://github.com/Supervisor/supervisor/issues/122>`_).
A workaround here would be to insert a wait loop in all the application programs (in the program command line
or in the program source code). The idea of pushing this wait loop outside the *Supervisor* scope - just before
starting ``supervisord`` - is excluded as it would impose this dependency on other applications eventually managed
by *Supervisor*.

With regard to **Requirement 7**, this workaround would require different program commands or parameters, so finally
different program definitions from *Supervisor* configuration perspective.

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

*Supervisor* provides nothing for **Requirement 3**. The user has to evaluate the operational status based on the process
status provided by the *Supervisor* instances on the 3 nodes, either using multiple ``supervisorctl`` shell commands,
XML-RPCs or event listeners.

To restart the whole application (**Requirement 5**), the user can perform ``supervisorctl`` shell commands or
XML-RPCs on each *Supervisor* instance.

.. code-block:: bash

    [bash] > for i in cliche81 cliche82 cliche83
    ... do
    ...    supervisorctl -s http://$i:<port> restart <group>:*
    ... done


Eventually, all the requirements could be met using *Supervisor* but it would require additional development
at application level to build an operational status, based on process information provided by *Supervisor*.

It would also require some additional complexity in the configuration files and in the program command lines
to manage a staged starting sequence of the programs in the group and to manage the distribution of the application
over different platforms.


Involving **Supvisors**
-----------------------

A solution based on **Supvisors** could use the following *Supervisor* configuration (same principles as the previous
section):

    * the ``supervisord_distributed.conf`` configuration file for the distributed application ;
    * the ``supervisord_localhost.conf`` configuration file for the non-distributed application ;
    * the program definitions and the group definition (``.ini`` files) for the first node ;
    * the program definitions and the group definition (``.ini`` files) for the second node ;
    * the program definitions and the group definition (``.ini`` files) for the third node ;
    * the group definition including all application programs for a local node.

All programs are now configured using ``autostart=false``.

About **Requirement 2**, **Supvisors** manages staged starting sequences and it offers a possibility to wait for a
planned exit of a process in the sequence.
So let's define a new program ``wait_nfs_mount_X`` per node and whose role is to exit (using an expected exit code,
as defined in `Supervisor program configuration <http://supervisord.org/configuration.html#program-x-section-values>`_)
as soon as the NFS mount is available.

Complying about **Requirement 7** is just about avoiding the inclusion of the ``wait_nfs_mount_X`` programs in the
*Supervisor* configuration file in the case of a non-distributed application. That's why the *Supervisor*
configuration of these programs is isolated from the configuration of the other programs.
THat way, **Supvisors** makes it possible to avoid an impact to program definitions, scripts and source code
when dealing with such a requirement.

Here follows what the include section may look like in both *Supervisor* configuration files.

.. code-block:: ini

    # include section for distributed application in supervisord_distributed.conf (unchanged)
    [include]
    files = %(host_node_name)s/*.ini

    # include section for non-distributed application in supervisord_localhost.conf
    # the same program definitions as the distributed application are used
    [include]
    files = %(host_node_name)s/programs_*.ini localhost/group_localhost.ini

Now that programs are not started automatically by *Supervisor*, a **Supvisors** rules file is needed to define
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
    when starting the ``scenario_1`` application. Then **Supvisors** waits for *all* of them to exit before it triggers
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
            <pattern name="cliche81_">
                <reference>model_cliche81</reference>
            </pattern>
            <program name="wait_nfs_mount_1">
                <reference>model_cliche81</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
            <!-- Programs on cliche82 -->
            <pattern name="cliche82_">
                <reference>model_cliche82</reference>
            </pattern>
            <program name="wait_nfs_mount_2">
                <reference>model_cliche82</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </program>
            <!-- Programs on cliche83 -->
            <pattern name="cliche83_">
                <reference>model_cliche83</reference>
            </pattern>
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
            <pattern name="">
                <addresses>cliche81</addresses>
                <start_sequence>1</start_sequence>
                <required>true</required>
            </pattern>
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
            <pattern name="">
                <reference>model_scenario_1</reference>
            </pattern>
            <pattern name="wait_nfs_mount">
                <reference>model_scenario_1</reference>
                <start_sequence>1</start_sequence>
                <wait_exit>true</wait_exit>
            </pattern>
        </application>
    </root>

Much shorter. Yet it does the same. For both the distributed application and the non-distributed application !

The main point is that the ``addresses`` attribute is not used at all. Clearly, this gives **Supvisors**
the authorization to start all programs on every nodes. However **Supvisors** knows about the *Supervisor* configuration
in the 3 nodes. When choosing a node to start a program, **Supvisors** considers the intersection between the authorized
nodes - all of them here - and the possible nodes, i.e. the active nodes where the program is defined in *Supervisor*.
One of the first decisions in this use case is that every programs are known to only one *Supervisor* instance so that
gives **Supvisors** only one possibility.

For **Requirement 3**, **Supvisors** provides the operational status of the application based on the status of its
processes, in accordance with their importance. In the present example, all programs are defined with the same
importance (``required`` set to ``true``). This status is made available through the **Supvisors**
:ref:`dashboard_application`, the :ref:`xml_rpc` and the :ref:`event_interface`.

The key point here is that **Supvisors** is able to build a single application from the processes configured
on the 3 nodes because the same group name (``scenario_1``) is used in all *Supervisor* configuration files.

.. image:: images/supvisors_scenario_1.png
    :alt: Supvisors Use Cases - Scenario 1
    :align: center

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

To restart the whole application (**Requirement 5**), the user can perform a single ``supervisorctl`` shell command
or a single XML-RPC on **Supvisors** from any node.

.. code-block:: bash

    [bash] > supervisorctl restart_application <strategy> <group>


As a conclusion, all the requirements are met using **Supvisors** and without any impact on the application to be
supervised. **Supvisors** brings gain over application control and status.


Example
-------

The full example is available in `Supvisors Use Cases - Scenario 1 <https://github.com/julien6387/supvisors/tree/master/supvisors/test/use_cases/scenario_1>`_.
