.. _scenario_3:

:program:`Scenario 3`
=====================

Context
-------

The application :program:`Scenario 3` is the control/command application referenced to in :program:`Scenario 2`.
It is delivered in 2 parts:

    * :program:`scen3_srv`: dedicated to application services and designed to run on a server only,
    * :program:`scen3_hci`: dedicated to Human Computer Interfaces (HCI) and designed to run on a console only.

Both :program:`scen3_hci` and :program:`scen3_srv` are started automatically.

:program:`scen3_srv` is unique and distributed over the servers.
One instance of the :program:`scen3_hci` application is started per console.

An internal data bus will allow all instances of :program:`scen3_hci` to communicate with :program:`scen3_srv`.

A common data bus - out of this application's scope - is available to exchange data between :program:`Scenario 3` and
other applications dealing with other types of items (typically as described in the use case :ref:`scenario_2`).


Requirements
------------

Here follows the use case requirements.

Global requirements
~~~~~~~~~~~~~~~~~~~

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

.. |Req 1| replace:: :program:`scen3_hci` and :program:`scen3_srv` shall be started automatically.
.. |Req 1 abbr| replace:: :abbr:`Requirement 1 (scen3_srv shall be started automatically.)`
.. |Req 2| replace:: An operational status of each application shall be provided.
.. |Req 2 abbr| replace:: :abbr:`Requirement 2 (An operational status of each application shall be provided.)`
.. |Req 3| replace:: :program:`scen3_hci` and :program:`scen3_srv` shall start only when their internal data bus is operational.
.. |Req 3 abbr| replace:: :abbr:`Requirement 3 (scen3_hci and scen3_srv shall start only when their internal data bus is operational.)`
.. |Req 4| replace:: The starting of :program:`scen3_hci` and :program:`scen3_srv` shall not be aborted in case of failure of one of its programs.
.. |Req 4 abbr| replace:: :abbr:`Requirement 4 (The starting of scen3_hci and scen3_srv shall not be aborted in case of failure of one of its programs.)`
.. |Req 5| replace:: Although the :program:`Scenario 3` is not directly concerned by resource limitations, it shall partake in the overall load information.
.. |Req 5 abbr| replace:: :abbr:`Requirement 5 (Although the Scenario 3 is not directly concerned by resource limitations, it shall partake in the overall load information.)`


Services requirements
~~~~~~~~~~~~~~~~~~~~~

Requirement 10
    |Req 10|

Requirement 11
    |Req 11|

Requirement 12
    |Req 12|

Requirement 13
    |Req 13|

Requirement 14
    |Req 14|

.. |Req 10| replace:: :program:`scen3_srv` shall be distributed on servers only.
.. |Req 10 abbr| replace:: :abbr:`Requirement 10 (scen3_srv shall be distributed on servers only.)`
.. |Req 11| replace:: There shall be a load-balancing strategy to distribute the :program:`scen3_srv` programs over the servers.
.. |Req 11 abbr| replace:: :abbr:`Requirement 11 (There shall be a load-balancing strategy to distribute the scen3_srv programs over the servers.)`
.. |Req 12| replace:: As :program:`scen3_srv` is distributed, its internal data bus shall be made available on all servers.
.. |Req 12 abbr| replace:: :abbr:`Requirement 12 (As scen3_srv is distributed, its internal data bus shall be made available on all servers.)`
.. |Req 13| replace:: Upon server power down or failure, the programs of :program:`scen3_srv` shall be re-distributed on the other servers, in accordance with the load-balancing strategy.
.. |Req 13 abbr| replace:: :abbr:`Requirement 13 (Upon server power down or failure, the programs of scen3_srv shall be re-distributed on the other servers, in accordance with the load-balancing strategy.)`
.. |Req 14| replace:: The :program:`scen3_srv` interface with the common data bus shall be started only when the common data bus is operational.
.. |Req 14 abbr| replace:: :abbr:`Requirement 14 (The scen3_srv interface with the common data bus shall be started only when the common data bus is operational.)`


HCI requirements
~~~~~~~~~~~~~~~~

Requirement 20
    |Req 20|

Requirement 21
    |Req 21|

.. |Req 20| replace:: A :program:`scen3_hci` shall be started on each console.
.. |Req 20 abbr| replace:: :abbr:`Requirement 20 (A scen3_hci shall be started on each console.)`
.. |Req 21| replace:: Upon console failure, :program:`scen3_hci` shall not be restarted on another console.
.. |Req 21 abbr| replace:: :abbr:`Requirement 21 (Upon console failure, scen3_hci shall not be restarted on another console.)`


Supervisor configuration
------------------------

The initial |Supervisor| configuration is as follows:

    * The ``bin`` folder includes all the program scripts of the :program:`Scenario 3` application.
      The scripts get the |Supervisor| ``program_name`` from the environment variable ``${SUPERVISOR_PROCESS_NAME}``.
    * The ``template_etc`` folder contains the generic configuration for the :program:`scen3_hci` group and programs.
    * The ``etc`` folder is the target destination for the configurations files of all applications to be supervised.
      It initially contains:

        - a definition of the common data bus (refer to |Req 14 abbr|) that will be auto-started on all |Supvisors|
          instances.
        - the configuration of the :program:`scen3_srv` group and programs.
        - the |Supervisor| configuration files that will be used when starting :program:`supervisord`:

            + the ``supervisord_console.conf`` includes the configuration files of the programs that are intended
              to run on the consoles,
            + the ``supervisord_server.conf`` includes the configuration files of the programs that are intended to run
              on the servers.

.. code-block:: bash

    [bash] > tree
    .
    ├── bin
    │         ├── chart_view.sh
    │         ├── check_common_data_bus.sh
    │         ├── check_internal_data_bus.sh
    │         ├── common_bus_interface.sh
    │         ├── common.sh
    │         ├── internal_data_bus.sh
    │         ├── item_control.sh
    │         ├── item_manager.sh
    │         └── track_manager.sh
    ├── etc
    │         ├── common
    │         │         └── group_services.ini
    │         ├── server
    │         │         └── group_server.ini
    │         ├── supervisord_console.conf
    │         └── supervisord_server.conf
    └── template_etc
        └── console
            └── group_hci.ini

The first update to the configuration is driven by the fact that the program :program:`internal_data_bus` is common to
:program:`scen3_srv` and :program:`scen3_hci`. As the :program:`Scenario 3` application may be distributed on all
consoles and servers (|Req 12 abbr| and |Req 20 abbr|), this program follows the same logic as the common data bus, so
let's remove it from :program:`scen3_srv` and :program:`scen3_hci` and to insert it into the common services.

Like the :program:`scen2_hci` of the :program:`Scenario 2`, :program:`scen3_hci` needs to be duplicated so this an
instance could be started on each console. In this example, there are 3 consoles. :program:`supvisors_breed` will thus
be used again to duplicate 3 times the :program:`scen3_hci` groups and programs found in the ``template_etc`` folder.

However, unlike :program:`Scenario 2` where any :program:`scen2_hci` could be started from any console, only one
:program:`scen3_hci` has to be started here per console and including more than one instance of it in the local
|Supervisor| is useless. So the option ``-x`` of :program:`supvisors_breed` will be used so that the duplicated
configurations are written into separated files in the ``etc`` folder. That will allow more flexibility when including
files from the |Supervisor| configuration file.

.. code-block:: bash

    [bash] > supvisors_breed -d etc -t template_etc -b scen3_hci=3 -x -v
    ArgumentParser: Namespace(breed={'scen3_hci': 3}, destination='etc', extra=True, pattern='**/*.ini', template='template_etc', verbose=True)
    Configuration files found:
        console/group_console.ini
        console/programs_console.ini
    Template group elements found:
        group:scen3_hci
    New File: console/group_scen3_hci_01.ini
    New [group:scen3_hci_01]
    New File: console/group_scen3_hci_02.ini
    New [group:scen3_hci_02]
    New File: console/group_scen3_hci_03.ini
    New [group:scen3_hci_03]
    Empty sections for file: console/group_console.ini
    Writing file: etc/console/programs_console.ini
    Writing file: etc/console/group_scen3_hci_01.ini
    Writing file: etc/console/group_scen3_hci_02.ini
    Writing file: etc/console/group_scen3_hci_03.ini

.. note:: *About the choice to prefix all program names with 'scen3_'*

    These programs are all included in a |Supervisor| group named ``scen3``. It may indeed seem useless to add the
    information into the program name. Actually the program names are quite generic and at some point the intention is
    to group all the applications of the different use cases into an unique |Supvisors| configuration. Adding ``scen3``
    at this point is just to avoid overwriting of program definitions.

Based on the expected names of the consoles, an additional script is used to sort the files generated.
The resulting file tree is as follows.

.. code-block:: bash

    [bash] > tree
    .
    ├── bin
    │         ├── chart_view.sh
    │         ├── check_common_data_bus.sh
    │         ├── check_internal_data_bus.sh
    │         ├── common_bus_interface.sh
    │         ├── common.sh
    │         ├── internal_data_bus.sh
    │         ├── item_control.sh
    │         ├── item_manager.sh
    │         ├── system_health.sh
    │         └── track_manager.sh
    ├── etc
    │         ├── common
    │         │         └── group_services.ini
    │         ├── console
    │         │         ├── console_1
    │         │         │         └── group_scen3_hci_01.ini
    │         │         ├── console_2
    │         │         │         └── group_scen3_hci_02.ini
    │         │         ├── console_3
    │         │         │         └── group_scen3_hci_03.ini
    │         │         └── programs_console.ini
    │         ├── server
    │         │         └── group_server.ini
    │         ├── supervisord_console.conf
    │         └── supervisord_server.conf
    └── template_etc
        └── console
            ├── group_console.ini
            └── programs_console.ini

Here follows what the include section may look like in both |Supervisor| configuration files.

.. code-block:: ini

    # include section in supervisord_server.conf
    [include]
    files = common/*.ini server/*.ini

    # include section in supervisord_console.conf
    [include]
    files = common/*.ini console/*.ini console/%(host_node_name)s/*.ini


Requirements met with |Supervisor| only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Based on the configuration defined above, |Supervisor| can definitely satisfy the following requirements: |Req 1 abbr|,
|Req 4 abbr|, |Req 10 abbr|, |Req 12 abbr|, |Req 20 abbr| and |Req 21 abbr|.

As already described in the previous use cases, requirements about operational status, staged start sequence and
automatic behaviour are out of |Supervisor|'s scope and would require dedicated software development to satisfy them.

Next section details how |Supvisors| can be used to deal with them.


Involving |Supvisors|
---------------------

As usual, when involving |Supvisors|, all :program:`Scenario 3` programs are configured using ``autostart=false``.
Exception is made to the programs in the ``etc/common`` folder (common and internal data buses).

The |Supvisors| configuration is built over the |Supervisor| configuration defined above.

Rules file
~~~~~~~~~~

As the logic of the starting sequence of :program:`Scenario 3` very similar to the :ref:`scenario_2` use case, there
won't be much detail about that in the present section. Please refer to the other use case if needed.

The main difference is that :program:`scen3_internal_data_bus` has been removed. As a reminder, the consequence of
|Req 12 abbr| and |Req 20 abbr| is that this program must run in all |Supvisors| instances, so it has been moved
to the services file and configured as auto-started.

Both applications :program:`scen3_srv` and :program:`scen3_hci` have their ``start_sequence`` set and strictly positive
so they will be automatically started, as required by |Req 1 abbr|. Please just note that :program:`scen3_hci` has a
greater ``start_sequence`` than :program:`scen3_srv` so it will be started only when :program:`scen3_srv` is fully
running.

|Req 3 abbr| and |Req 14 abbr| are satisfied by the following programs that are configured with a ``wait_exit`` option:

    * :program:`scen3_check_internal_data_bus` and :program:`scen3_check_common_data_bus` for :program:`scen3_srv`.
    * :program:`scen3_check_internal_data_bus` for :program:`scen3_hci`

The ``distribution`` options is not set for the :program:`scen3_srv` application. As it is defaulted to ``true`` and as
all :program:`scen3_srv` programs are configured with the ``identifiers`` option set with the servers alias,
:program:`scen3_srv` will be distributed over the servers when starting, as required by |Req 10 abbr|.

The ``distribution`` options is set to ``false`` for the :program:`scen3_hci`. In this case, only the ``identifiers``
option set to the application element is taken into account and NOT the ``identifiers`` options set to the program
elements. The value ``#,consoles`` used here needs some further explanation.

When using hashtags in ``identifiers``, applications and programs cannot be started anywhere until |Supvisors| solves
the 'equation'. As defined in :ref:`patterns_hashtags`, an association will be made between the Nth application
:program:`scen3_hci_N` and the Nth element of the ``consoles`` list. In the example, :program:`scen3_hci_01` will be
mapped with |Supvisors| instance ``console_1`` once resolved.

This will result in having exactly one :program:`scen3_hci` application per console, which satisfies |Req 20 abbr|.

.. note::

    In :program:`scen3_hci`, the program ``scen3_check_internal_data_bus`` references a model that uses server
    |Supvisors| instances in its ``identifiers`` option. It doesn't matter in the present case because, as told before,
    the ``identifiers`` option of the non-distributed application supersedes the ``identifiers`` eventually set in its
    programs.

Let's now focus on the strategies and options used at application level.

In accordance with |Req 4 abbr|, the ``starting_failure_strategy`` option of both :program:`scen3_srv` and
:program:`scen3_hci` are set to CONTINUE (default is ``ABORT``).

To satisfy |Req 13 abbr|, the ``running_failure_strategy`` option of :program:`scen3_srv` has been set to
``RESTART_PROCESS`` (via the model ``model_services``). For :program:`scen3_hci`, this option is not set and the default
``CONTINUE`` is then used, as required in |Req 21 abbr|. Anyway, as the Nth application si only known by the
|Supervisor| of the Nth console, it is just impossible to start this application elsewhere.

Finally, in order to satisfy |Req 5 abbr| and to have a load-balancing over the server |Supvisors| instances (refer to
|Req 11 abbr|), an arbitrary ``expected_loading`` has been set on programs. It is expected that relevant figures are
used for a real application.
The ``starting_strategy`` option of :program:`scen3_srv` has been set to ``LESS_LOADED``.

Here follows the resulting rules file.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <!-- aliases -->
        <alias name="servers">server_1,server_2,server_3</alias>
        <alias name="consoles">console_1,console_2,console_3</alias>

        <!-- models -->
        <model name="model_services">
            <identifiers>servers</identifiers>
            <start_sequence>2</start_sequence>
            <required>true</required>
            <expected_loading>2</expected_loading>
            <running_failure_strategy>RESTART_PROCESS</running_failure_strategy>
        </model>
        <model name="check_data_bus">
            <identifiers>servers</identifiers>
            <start_sequence>1</start_sequence>
            <required>true</required>
            <wait_exit>true</wait_exit>
        </model>

        <!-- Scenario 3 Applications -->
        <!-- Services -->
        <application name="scen3_srv">
            <start_sequence>1</start_sequence>
            <starting_strategy>LESS_LOADED</starting_strategy>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <programs>
                <program name="scen3_common_bus_interface">
                    <reference>model_services</reference>
                    <start_sequence>3</start_sequence>
                </program>
                <program name="scen3_check_common_data_bus">
                    <reference>check_data_bus</reference>
                    <start_sequence>2</start_sequence>
                </program>
                <program pattern="">
                    <reference>model_services</reference>
                </program>
                <program name="scen3_check_internal_data_bus">
                    <reference>check_data_bus</reference>
                </program>
            </programs>
        </application>

        <!-- HCI -->
        <application pattern="scen3_hci_">
            <distribution>SINGLE_INSTANCE</distribution>
            <identifiers>#,consoles</identifiers>
            <start_sequence>3</start_sequence>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <programs>
                <program pattern="">
                    <start_sequence>2</start_sequence>
                    <expected_loading>8</expected_loading>
                </program>
                <program name="scen3_check_internal_data_bus">
                    <reference>check_data_bus</reference>
                </program>
            </programs>
        </application>

    </root>


Control & Status
~~~~~~~~~~~~~~~~

The operational status of :program:`Scenario 3` required by the |Req 2 abbr| is made available through:

    * the :ref:`dashboard_application` of the |Supvisors| Web UI, as a LED near the application state,
    * the :ref:`xml_rpc` (example below),
    * the :ref:`rest_api` (if :program:`supvisorsflask` is started),
    * the :ref:`extended_status` of the extended :program:`supervisorctl` or :program:`supvisorsctl` (example below),
    * the :ref:`event_interface`.

For the examples, the following context applies:

    * due to limited resources - 3 nodes are available (``rocky51``, ``rocky52`` and ``rocky53``) -, each node hosts
      2 |Supvisors| instances, one server and one console ;
    * :program:`common_data_bus` and :program:`scen3_internal_data_bus` are *Unmanaged* so |Supvisors| always considers
      these 'applications' as ``STOPPED`` ;
    * :program:`scen3_srv` is distributed over the 3 servers ;
    * :program:`scen3_hci_01`,program:`scen3_hci_02`, program:`scen3_hci_03` have been respectively started on
      ``console_1``, ``console_2``, ``console_3`` .

The |Supervisor| configuration of the consoles has been changed to include the files related to the |Supervisor|
identifier ``console_X`` rather than those related to ``host_node_name``. As there is no automatic expansion related
to the |Supervisor| identifier so far, an environmental variable is used.

.. code-block:: ini

    # include section in supervisord_console.conf
    [include]
    files = common/*.ini console/*.ini console/%(ENV_IDENTIFIER)s/*.ini

>>> from supervisor.childutils import getRPCInterface
>>> proxy = getRPCInterface({'SUPERVISOR_SERVER_URL': 'http://localhost:61000'})
>>> proxy.supvisors.get_all_applications_info()
[{'application_name': 'common_data_bus', 'statecode': 0, 'statename': 'STOPPED', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen3_internal_data_bus', 'statecode': 0, 'statename': 'STOPPED', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen3_srv', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen3_hci_01', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen3_hci_02', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen3_hci_03', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False}]

.. code-block:: bash

    [bash] > supvisorsctl -s http://localhost:61000 application_info
    Application              State     Major  Minor
    common_data_bus          STOPPED   False  False
    scen3_internal_data_bus  STOPPED   False  False
    scen3_srv                RUNNING   False  False
    scen3_hci_01             RUNNING   False  False
    scen3_hci_02             RUNNING   False  False
    scen3_hci_03             RUNNING   False  False

.. image:: images/supvisors_scenario_3.png
    :alt: Supvisors Use Cases - Scenario 3
    :align: center

As a conclusion, all the requirements are met using |Supvisors| and without any impact on the application to be
supervised. |Supvisors| improves application control and status.


Example
-------

The full example is available in `Supvisors Use Cases - Scenario 3 <https://github.com/julien6387/supvisors/tree/master/supvisors/test/use_cases/scenario_3>`_.

Two versions are provided:

    * one corresponding to the description above ;
    * one based on the |Supvisors| discovery mode, using stereotypes rather than aliases.

.. include:: common.rst
