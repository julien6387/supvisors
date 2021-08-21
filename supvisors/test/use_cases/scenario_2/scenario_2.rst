.. _scenario_2:

Scenario 2
==========

Context
-------

In this use case, the application "Scenario2" is used to control an item.
It is delivered in 2 parts:

    * :program:`scen2_srv`: dedicated to services and designed to run on a server only,
    * :program:`scen2_hci`: dedicated to Human Computer Interfaces (HCI) and designed to run on a console only.

:program:`scen2_hci` is started on demand from a console, whereas :program:`scen2_srv` is available on startup.
:program:`scen2_srv` cannot be distributed because of its inter-processes communication scheme.
:program:`scen2_hci` is not distributed so that the user gets all the windows on the same screen.
An internal data bus will allow :program:`scen2_hci` to communicate with :program:`scen2_srv`.

Multiple instances of the "Scenario2" application can be started because there are multiple items to control.

A common data bus - out of this application's scope - is available to exchange data between "Scenario2" instances
and other applications dealing with other types of items and/or a higher control/command application.


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

.. |Req 1| replace:: Given X items to control, it shall be possible to start X instances of the application.
.. |Req 1 abbr| replace:: :abbr:`Requirement 1 (Given X items to control, it shall be possible to start X instances of the application.)`
.. |Req 2| replace:: :program:`scen2_hci` and :program:`scen2_srv` shall not be distributed.
.. |Req 2 abbr| replace:: :abbr:`Requirement 2 (scen2_hci and scen2_srv shall not be distributed.)`
.. |Req 3| replace:: An operational status of each application shall be provided.
.. |Req 3 abbr| replace:: :abbr:`Requirement 3 (An operational status of each application shall be provided.)`
.. |Req 4| replace:: :program:`scen2_hci` and :program:`scen2_srv` shall start only when their internal data bus is operational.
.. |Req 4 abbr| replace:: :abbr:`Requirement 4 (scen2_hci and scen2_srv shall start only when their internal data bus is operational.)`
.. |Req 5| replace:: The number of application instances running shall be limited in accordance with the resources available (consoles or servers up).
.. |Req 5 abbr| replace:: :abbr:`Requirement 5 (The number of application instances running shall be limited in accordance with the resources available (consoles or servers up).)`


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

Requirement 15
    |Req 15|

Requirement 16
    |Req 16|

Requirement 17
    |Req 17|

.. |Req 10| replace:: :program:`scen2_srv` shall be started on servers only.
.. |Req 10 abbr| replace:: :abbr:`Requirement 10 (scen2_srv shall be started on servers only.)`
.. |Req 11| replace:: The X :program:`scen2_srv` shall be started automatically.
.. |Req 11 abbr| replace:: :abbr:`Requirement 11 (The X scen2_srv shall be started automatically.)`
.. |Req 12| replace:: Each :program:`scen2_srv` shall be started once at most.
.. |Req 12 abbr| replace:: :abbr:`Requirement 12 (Each scen2_srv shall be started once at most.)`
.. |Req 13| replace:: There shall be a load-balancing strategy to distribute the X :program:`scen2_srv` over the servers.
.. |Req 13 abbr| replace:: :abbr:`Requirement 13 (There shall be a load-balancing strategy to distribute the X scen2_srv over the servers.)`
.. |Req 14| replace:: Upon failure in its starting sequence, :program:`scen2_srv` shall be stopped so that it doesn't consume resources uselessly.
.. |Req 14 abbr| replace:: :abbr:`Requirement 14 (Upon failure in its starting sequence, scen2_srv shall be stopped so that it doesn't consume resources uselessly.)`
.. |Req 15| replace:: As :program:`scen2_srv` is highly dependent on its internal data bus, :program:`scen2_srv` shall be fully restarted if its internal data bus crashes.
.. |Req 15 abbr| replace:: :abbr:`Requirement 15 (As scen2_srv is highly dependent on its internal data bus, scen2_srv shall be fully restarted if its internal data bus crashes.)`
.. |Req 16| replace:: Upon server failure, :program:`scen2_srv` shall be restarted on another server, in accordance with the load-balancing strategy.
.. |Req 16 abbr| replace:: :abbr:`Requirement 16 (Upon server failure, scen2_srv shall be restarted on another server, in accordance with the load-balancing strategy.)`
.. |Req 17| replace:: The :program:`scen2_srv` interface with the common data bus shall be started only when the common data bus is operational.
.. |Req 17 abbr| replace:: :abbr:`Requirement 17 (The scen2_srv interface with the common data bus shall be started only when the common data bus is operational.)`


HCI requirements
~~~~~~~~~~~~~~~~

Requirement 20
    |Req 20|

Requirement 21
    |Req 21|

Requirement 22
    |Req 22|

Requirement 23
    |Req 23|

Requirement 24
    |Req 24|

Requirement 25
    |Req 25|

Requirement 26
    |Req 26|

Requirement 27
    |Req 27|

.. |Req 20| replace:: A :program:`scen2_hci` shall be started upon user request.
.. |Req 20 abbr| replace:: :abbr:`Requirement 20 (A scen2_hci shall be started upon user request.)`
.. |Req 21| replace:: The :program:`scen2_hci` shall be started on the console from where the user request has been done.
.. |Req 21 abbr| replace:: :abbr:`Requirement 21 (The scen2_hci shall be started on the console from where the user request has been done.)`
.. |Req 22| replace:: When starting a :program:`scen2_hci`, the user shall choose the item to control.
.. |Req 22 abbr| replace:: :abbr:`Requirement 22 (When starting a scen2_hci, the user shall choose the item to control.)`
.. |Req 23| replace:: The user shall not be able to start two :program:`scen2_hci` that control the same item.
.. |Req 23 abbr| replace:: :abbr:`Requirement 23 (The user shall not be able to start two scen2_hci that control the same item.)`
.. |Req 24| replace:: Upon failure, the starting sequence of :program:`scen2_hci` shall continue.
.. |Req 24 abbr| replace:: :abbr:`Requirement 24 (Upon failure, the starting sequence of scen2_hci shall continue.)`
.. |Req 25| replace:: As :program:`scen2_hci` is highly dependent on its internal data bus, :program:`scen2_hci` shall be fully stopped if its internal data bus crashes.
.. |Req 25 abbr| replace:: :abbr:`Requirement 25 (As scen2_hci is highly dependent on its internal data bus, scen2_hci shall be fully stopped if its internal data bus crashes.)`
.. |Req 26| replace:: Upon console failure, :program:`scen2_hci` shall not be restarted on another console.
.. |Req 26 abbr| replace:: :abbr:`Requirement 26 (Upon console failure, scen2_hci shall not be restarted on another console.)`
.. |Req 27| replace:: :program:`scen2_hci` shall be stopped upon user request.
.. |Req 27 abbr| replace:: :abbr:`Requirement 27 (scen2_hci shall be stopped upon user request.)`


Supervisor configuration
------------------------

The initial |Supervisor| configuration is as follows:

    * The ``bin`` folder includes all the program scripts of the "Scenario2" application.
      The scripts get the |Supervisor| ``program_name`` from the environment variable ``${SUPERVISOR_PROCESS_NAME}``.
    * The ``template_etc`` folder contains the generic configuration for the "Scenario2" application:

        - the ``console/group_hci.ini`` file that contains the definition of the :program:`scen2_hci` group
          and programs,
        - the ``server/group_server.ini`` file that contains the definition of the :program:`scen2_srv` group
          and programs.

    * The ``etc`` folder is the target destination for the configurations files of all applications to be supervised.
      In this example, it just contains a definition of the common data bus (refer to |Req 17 abbr|) that will be
      auto-started on all nodes.
      The ``etc`` folder contains the |Supervisor| configuration files that will be used when starting
      :program:`supervisord`.

        - the ``supervisord_console.conf`` includes the definition of groups and programs that are intended to run
          on the consoles,
        - the ``supervisord_server.conf`` includes the definition of groups and programs that are intended to run
          on the servers.

.. code-block:: bash

    [bash] > tree
    .
    ├── bin
    │         ├── common_bus_interface.sh
    │         ├── common_check_data_bus.sh
    │         ├── common.sh
    │         ├── config_manager.sh
    │         ├── data_processing.sh
    │         ├── internal_check_data_bus.sh
    │         ├── internal_data_bus.sh
    │         ├── sensor_acquisition.sh
    │         ├── sensor_control.sh
    │         └── sensor_view.sh
    ├── etc
    │         ├── common
    │         │         └── services.ini
    │         ├── supervisord_console.conf
    │         └── supervisord_server.conf
    └── template_etc
        ├── console
        │         └── group_hci.ini
        └── server
            └── group_server.ini


Homogeneous applications
~~~~~~~~~~~~~~~~~~~~~~~~

Let's tackle the first big issue about |Req 1 abbr|. |Supervisor| does not provide any support to handle *homogeneous*
groups. It only provides support for *homogeneous* process groups. Defining *homogeneous* process groups in the present
case won't help as the program instances cannot be shared across multiple groups.

Assuming that the "Scenario2" application is delivered with the |Supervisor| configuration files for one generic item
to control and assuming that there are X items to control, the first job is duplicate X times all programs and groups
definitions.

This may be a bit painful when X is great, so a script is provided in the |Supvisors| package to make life easier.
The next section will detail how it will be used.

.. code-block:: bash

    [bash] > cd /usr/local/lib/python3.6/site-packages/supvisors/tools/
    [bash] > python breed.py -h
    usage: breed.py [-h] -t TEMPLATE [-p PATTERN] -d DESTINATION
                    [-b app=nb [app=nb ...]] [-v]

    Duplicate the application definitions

    optional arguments:
      -h, --help            show this help message and exit
      -t TEMPLATE, --template TEMPLATE
                            the template folder
      -p PATTERN, --pattern PATTERN
                            the search pattern from the template folder
      -d DESTINATION, --destination DESTINATION
                            the destination folder
      -b app=nb [app=nb ...], --breed app=nb [app=nb ...]
                            the applications to breed
      -v, --verbose         activate logs

For this example, let's stick to X=3. Using greater values don't change the complexity of what follows. It would just
need more resources to test.
The :program:`breed` script duplicates 3 times the :program:`scen2_srv` and :program:`scen2_hci` groups and programs
found in the ``template_etc`` folder and writes new configuration files into the ``etc`` folder.

.. code-block:: bash

    [bash] > python ../../../tools/breed.py -d etc -t template_etc -b scen2_srv=3 scen2_hci=3 -v
    ArgumentParser: Namespace(breed={'scen2_srv': 3, 'scen2_hci': 3}, destination='etc', pattern='**/*.ini', template='template_etc', verbose=True)
    Configuration files found:
        console/group_hci.ini
        server/group_server.ini
    Template elements found:
        group:scen2_hci
        program:chart_view
        program:sensor_control
        program:sensor_view
        program:hci_internal_check_data_bus
        program:hci_internal_data_bus
        group:scen2_srv
        program:config_manager
        program:common_check_data_bus
        program:common_bus_interface
        program:internal_check_data_bus
        program:internal_data_bus
        program:data_processing
        program:sensor_acquisition
    New [group:scen2_srv_01]
        programs=config_manager_01,common_bus_interface_01,common_check_data_bus_01,internal_check_data_bus_01,internal_data_bus_01,data_processing_01,sensor_acquisition_01
    New [group:scen2_srv_02]
        programs=config_manager_02,common_bus_interface_02,common_check_data_bus_02,internal_check_data_bus_02,internal_data_bus_02,data_processing_02,sensor_acquisition_02
    New [group:scen2_srv_03]
        programs=config_manager_03,common_bus_interface_03,common_check_data_bus_03,internal_check_data_bus_03,internal_data_bus_03,data_processing_03,sensor_acquisition_03
    New [group:scen2_hci_01]
        programs=chart_view_01,sensor_control_01,sensor_view_01,hci_internal_check_data_bus_01,hci_internal_data_bus_01
    New [group:scen2_hci_02]
        programs=chart_view_02,sensor_control_02,sensor_view_02,hci_internal_check_data_bus_02,hci_internal_data_bus_02
    New [group:scen2_hci_03]
        programs=chart_view_03,sensor_control_03,sensor_view_03,hci_internal_check_data_bus_03,hci_internal_data_bus_03

The resulting file tree is as follows.

.. code-block:: bash

    [bash] > tree
    .
    ├── bin
    │         ├── common_bus_interface.sh
    │         ├── common_check_data_bus.sh
    │         ├── common.sh
    │         ├── config_manager.sh
    │         ├── data_processing.sh
    │         ├── internal_check_data_bus.sh
    │         ├── internal_data_bus.sh
    │         ├── sensor_acquisition.sh
    │         ├── sensor_control.sh
    │         └── sensor_view.sh
    ├── etc
    │         ├── common
    │         │         └── services.ini
    │         ├── console
    │         │         └── group_hci.ini
    │         ├── server
    │         │         └── group_server.ini
    │         ├── supervisord_console.conf
    │         └── supervisord_server.conf
    └── template_etc
        ├── console
        │         └── group_hci.ini
        └── server
            └── group_server.ini

.. note::

    As a definition, let's say that the combination of ``scen2_srv_01`` and ``scen2_hci_01`` is the "Scenario2"
    application that controls the item 01.

Here follows what the include section may look like in both |Supervisor| configuration files.

.. code-block:: ini

    # include section in supervisord_server.conf
    [include]
    files = common/*.ini server/*.ini

    # include section in supervisord_console.conf
    [include]
    files = common/*.ini console/*.ini

From this point, the ``etc`` folder contains the |Supervisor| configuration that satisfies |Req 1 abbr|.


Requirements met with |Supervisor| only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Server side
***********

|Req 10 abbr| is satisfied by the ``supervisord_[server|console].conf`` files. Only the ``supervisord_server.conf`` file
holds the information to start :program:`scen2_srv`.

|Req 16 abbr| implies that all :program:`scen2_srv` definitions must be available on all servers. So a single
``supervisord_server.conf`` including all :program:`scen2_srv` definitions and made available on all servers still
makes sense.

The automatic start required in |Req 11 abbr| could be achieved by using the |Supervisor| ``autostart=True``
on the programs but considering |Req 2 abbr| and |Req 12 abbr|, that becomes a bit complex.

It looks like 2 sets of program definitions are needed, one definition with ``autostart=True``
and one with ``autostart=False``. All :program:`scen2_srv` groups must include program definitions with a homogeneous
use of ``autostart``.

In order to maintain the load balancing required in |Req 13 abbr|, the user must define in advance which
:program:`scen2_srv` shall run on which server and use the relevant program definition (``autostart``-dependent).

This all ends up with a dedicated ``supervisord_server_S.conf`` configuration file for each server.

Console side
************

Now let's look at the console side.
Like for the server configuration, all :program:`scen2_hci` must be available on all consoles to satisfy |Req 22 abbr|.
Per definition, choosing one of the :program:`scen2_hci` is a way to choose the item to control.

|Req 20 abbr|, |Req 21 abbr| and |Req 27 abbr| are simply met using :program:`supervisorctl` commands.

.. code-block:: bash

    [bash] > supervisorctl start scen2_hci_01:*
    [bash] > supervisorctl stop scen2_hci_01:*

It is possible to do that from the |Supervisor| web UI too, one program at a time.
Clumsy and there's a risk of mistakes.

Of course, the use of commands like :program:`supervisorctl -s http://other_console:port` should be prohibited.

However, there's nothing to prevent another user to start the same ``scen2_hci`` on his console, as required in
|Req 23 abbr|.

All the other requirements are about automatic behaviour and there's no |Supervisor| function for that.
It would require software dedicated development to satisfy them.
Or |Supvisors| may be used, which is the point of the next section.


Involving |Supvisors|
---------------------

When involving |Supvisors|, all "Scenario2" programs are configured using ``autostart=false``.
Only the common data bus - that is outside of the application scope - will be auto-started.

The |Supvisors| configuration is built over the |Supervisor| configuration defined above.

Rules file
~~~~~~~~~~

All the requirements about automatic behaviour are dealt in the |Supvisors| rules file. This section will detail step
by step how it is built against the requirements.

First, as all ``scen2_srv`` instances have the same rules, a single application entry with a matching pattern is used
for all of them. The same idea applies to ``scen2_hci``.
Declaring these applications in the |Supvisors| rules file makes them all *Managed* in |Supvisors|, which gives control
over the X instances of the "Scenario2" application, as required in |Req 1 abbr|.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <application pattern="scen2_srv_"/>
        <application pattern="scen2_hci_"/>
    </root>

|Req 2 abbr| is just about declaring the ``distributed`` element to ``false``. It tells |Supvisors| that all the
programs of the application have to be started on the same node.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <application pattern="scen2_srv_">
            <distributed>false</distributed>
        </application>

        <application pattern="scen2_hci_">
            <distributed>false</distributed>
        </application>
    </root>

So far, all applications can be started on any node. Let's compel ``scen2_hci`` to consoles and ``scen2_srv`` to
servers, which satisfies |Req 10 abbr| and contributes to some console-related requirements.
For better readability, node aliases are introduced.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <alias name="servers">cliche81,cliche82,cliche85</alias>
        <alias name="consoles">cliche83,cliche84,cliche86,cliche87,cliche88</alias>

        <application pattern="scen2_srv_">
            <distributed>false</distributed>
            <addresses>servers</addresses>
        </application>

        <application pattern="scen2_hci_">
            <distributed>false</distributed>
            <addresses>consoles</addresses>
        </application>
    </root>

It's time to introduce the staged start sequences. |Req 11 abbr| asks for an automatic start of ``scen2_srv``, so
a strictly positive ``start_sequence`` is added to the application configuration.

Because of |Req 4 abbr|, ``scen2_srv`` and ``scen2_hci`` applications will be started in three phases:

    * first the ``internal_data_bus_X`` program,
    * then the ``internal_check_data_bus_X`` whose job is to periodically check the ``internal_data_bus_X`` status and
      exit when it is operational,
    * other programs.

``internal_data_bus_X`` and ``internal_check_data_bus_X`` are common to ``scen2_srv`` and ``scen2_hci`` and follow
the same rules so it make sense to define a common model for them.

Due to |Req 17 abbr|, two additional phases are needed for ``scen2_srv``:

    * the ``common_check_data_bus_X`` whose job is to periodically check the ``common_data_bus`` status and exit
      when it is operational,
    * finally the ``common_bus_interface_X``.

They are set at the end of the starting sequence so that the core of the ``scen2_srv`` application can be operational
as a standalone application, even if it's not connected to other possible applications in the system.

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <alias name="servers">cliche81,cliche82,cliche85</alias>
        <alias name="consoles">cliche83,cliche84,cliche86,cliche87,cliche88</alias>

        <model name="model_services">
            <start_sequence>3</start_sequence>
            <required>true</required>
        </model>
        <model name="check_data_bus">
            <start_sequence>2</start_sequence>
            <required>true</required>
            <wait_exit>true</wait_exit>
        </model>
        <model name="data_bus">
            <start_sequence>1</start_sequence>
            <required>true</required>
        </model>

        <application pattern="scen2_srv_">
            <distributed>false</distributed>
            <addresses>servers</addresses>
            <start_sequence>1</start_sequence>

            <program pattern="common_bus_interface">
                <reference>model_services</reference>
                <start_sequence>4</start_sequence>
            </program>
            <program pattern="common_check_">
                <reference>check_data_bus</reference>
                <start_sequence>3</start_sequence>
            </program>
            <pattern name="">
                <reference>model_services</reference>
            </pattern>
            <program pattern="internal_check_">
                <reference>check_data_bus</reference>
            </program>
            <program pattern="internal_data_bus">
                <reference>data_bus</reference>
            </program>
        </application>

        <application pattern="scen2_hci_">
            <distributed>false</distributed>
            <addresses>consoles</addresses>

            <program pattern="">
                <start_sequence>3</start_sequence>
            </program>
            <program pattern="internal_check_">
                <reference>check_data_bus</reference>
            </program>
            <program pattern="internal_data_bus">
                <reference>data_bus</reference>
            </program>
        </application>
    </root>

.. attention::

    When using application patterns, it is recommended to include only program patterns unless the consequence is well
    understood. Indeed, using a program name is correct but it will match only one process of one application.

.. hint::

    In the rules file, several program patters are used, including empty patterns. As a rule, given a program name to
    match, |Supvisors| always chooses the most specific pattern.

Let's now introduce the automatic behaviors.

|Req 5 abbr| implies to check the resources available before allowing an application or a program to be started.
|Supvisors| has been designed to consider the resources needed by the program over the resources actually taken.
To achieve that, the ``expected_loading`` elements of the programs have been set (quite arbitrarily for the example).

The ``starting_strategy`` element of the ``scen2_srv`` application is set to ``LESS_LOADED`` to satisfy |Req 13 abbr|.
Before |Supvisors| starts a program or an application, it relies on the ``expected_loading`` set just before to:

    * evaluate the current load on all nodes (due to processes already running)
    * choose the node having the lowest load and that can accept the additional load required by the program
      or application to start,
    * if none found, the application and/or the program is not started, which satisfies |Req 5 abbr| .

The ``starting_strategy`` element of the ``scen2_hci`` application is set to ``LOCAL`` to satisfy |Req 21 abbr|.
Actually this value is only used as a default parameter in the :ref:`dashboard_application` of the |Supvisors| Web UI
and can be overridden.

|Req 14 abbr| starting failure strategy = STOP_APPLICATION
|Req 24 abbr| starting failure strategy = CONTINUE

|Req 15 abbr| internal_data_bus running failure strategy = RESTART_APPLICATION
|Req 25 abbr| internal_data_bus running failure strategy = STOP_APPLICATION

|Req 3 abbr| operational status

.. code-block:: xml

    <?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <root>
        <!-- aliases -->
        <alias name="servers">cliche81,cliche82,cliche85</alias>
        <alias name="consoles">cliche83,cliche84,cliche86,cliche87,cliche88</alias>

        <!-- models -->
        <model name="model_services">
            <start_sequence>3</start_sequence>
            <required>true</required>
            <expected_loading>10</expected_loading>
        </model>
        <model name="check_data_bus">
            <start_sequence>2</start_sequence>
            <required>true</required>
            <wait_exit>true</wait_exit>
        </model>
        <model name="data_bus">
            <start_sequence>1</start_sequence>
            <required>true</required>
            <expected_loading>2</expected_loading>
        </model>

        <!-- Scenario 2 Applications -->
        <!-- Services -->
        <application pattern="scen2_srv_">
            <distributed>false</distributed>
            <addresses>servers</addresses>
            <start_sequence>1</start_sequence>
            <starting_strategy>LESS_LOADED</starting_strategy>
            <starting_failure_strategy>STOP</starting_failure_strategy>
            <program pattern="common_bus_interface">
                <reference>model_services</reference>
                <start_sequence>4</start_sequence>
            </program>
            <program pattern="common_check_">
                <reference>check_data_bus</reference>
                <start_sequence>3</start_sequence>
            </program>
            <pattern name="">
                <reference>model_services</reference>
            </pattern>
            <program pattern="internal_check_">
                <reference>check_data_bus</reference>
            </program>
            <program pattern="internal_data_bus">
                <reference>data_bus</reference>
                <running_failure_strategy>RESTART_APPLICATION</running_failure_strategy>
            </program>
        </application>

        <!-- HCI -->
        <application pattern="scen2_hci_">
            <distributed>false</distributed>
            <addresses>consoles</addresses>
            <starting_strategy>LOCAL</starting_strategy>
            <starting_failure_strategy>CONTINUE</starting_failure_strategy>
            <program pattern="">
                <start_sequence>3</start_sequence>
                <expected_loading>8</expected_loading>
            </program>
            <program pattern="internal_check_">
                <reference>check_data_bus</reference>
            </program>
            <program pattern="internal_data_bus">
                <reference>data_bus</reference>
                <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
            </program>
        </application>

    </root>

no impact
|Req 16 abbr| not distributed => all app stopped + internal_data_bus running failure strategy = RESTART_APPLICATION + starting strategy = LESS_LOADED
|Req 26 abbr| default running failure strategy is CONTINUE. only RESTART_APPLICATION or RESTART_PROCESS would restart something elsewhere


|Supvisors| Web UI
~~~~~~~~~~~~~~~~~~

use Web UI but supervisorctl ok

Status
|Req 3 abbr| operational status

Control
|Req 20 abbr| + |Req 22 abbr| choix appli X sur web UI
|Req 12| + |Req 23 abbr| max une instance running
|Req 27 abbr| stop appli web UI


.. image:: images/supvisors_scenario_2.png
    :alt: Supvisors Use Cases - Scenario 2
    :align: center

As a conclusion, all the requirements are met using |Supvisors| and without any impact on the application to be
supervised. |Supvisors| brings gain over application control and status.


Example
-------

The full example is available in `Supvisors Use Cases - Scenario 2 <https://github.com/julien6387/supvisors/tree/master/supvisors/test/use_cases/scenario_2>`_.

.. include:: common.rst
