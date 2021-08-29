.. _scenario_2:

:program:`Scenario 2`
=====================

Context
-------

In this use case, the application :program:`Scenario 2` is used to control an item.
It is delivered in 2 parts:

    * :program:`scen2_srv`: dedicated to application services and designed to run on a server only,
    * :program:`scen2_hci`: dedicated to Human Computer Interfaces (HCI) and designed to run on a console only.

:program:`scen2_hci` is started on demand from a console, whereas :program:`scen2_srv` is available on startup.
:program:`scen2_srv` cannot be distributed because of its inter-processes communication scheme.
:program:`scen2_hci` is not distributed so that the user gets all the windows on the same screen.
An internal data bus will allow :program:`scen2_hci` to communicate with :program:`scen2_srv`.

Multiple instances of the :program:`Scenario 2` application can be started because there are multiple items to control.

A common data bus - out of this application's scope - is available to exchange data between :program:`Scenario 2`
instances and other applications dealing with other types of items and/or a higher control/command application (as
described in :ref:`scenario_3`).


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
.. |Req 16| replace:: Upon server power down or failure, :program:`scen2_srv` shall be restarted on another server, in accordance with the load-balancing strategy.
.. |Req 16 abbr| replace:: :abbr:`Requirement 16 (Upon server power down or failure, scen2_srv shall be restarted on another server, in accordance with the load-balancing strategy.)`
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

    * The ``bin`` folder includes all the program scripts of the :program:`Scenario 2` application.
      The scripts get the |Supervisor| ``program_name`` from the environment variable ``${SUPERVISOR_PROCESS_NAME}``.
    * The ``template_etc`` folder contains the generic configuration for the :program:`Scenario 2` application:

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
    │         ├── check_common_data_bus.sh
    │         ├── check_internal_data_bus.sh
    │         ├── common_bus_interface.sh
    │         ├── common.sh
    │         ├── config_manager.sh
    │         ├── data_processing.sh
    │         ├── internal_data_bus.sh
    │         ├── sensor_acquisition.sh
    │         ├── sensor_control.sh
    │         └── sensor_view.sh
    ├── etc
    │         ├── common
    │         │         └── group_services.ini
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

Assuming that the :program:`Scenario 2` application is delivered with the |Supervisor| configuration files for one
generic item to control and assuming that there are X items to control, the first job is duplicate X times all programs
and groups definitions.

This may be a bit painful when X is great, so a script is provided in the |Supvisors| package to make life easier.

.. code-block:: bash

    [bash] > supvisors_breed -h
    usage: supvisors_breed [-h] -t TEMPLATE [-p PATTERN] -d DESTINATION
                    [-b app=nb [app=nb ...]] [-x] [-v]

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
      -x, --extra           create new files
      -v, --verbose         activate logs

For this example, let's define X=3. Using greater values don't change the complexity of what follows. It would just
need more resources to test.
:program:`supvisors_breed` duplicates 3 times the :program:`scen2_srv` and :program:`scen2_hci` groups and programs
found in the ``template_etc`` folder and writes new configuration files into the ``etc`` folder.

.. code-block:: bash

    [bash] > supvisors_breed -d etc -t template_etc -p server/*.ini -b scen2_srv=3 -x -v
    ArgumentParser: Namespace(breed={'scen2_srv': 3}, destination='etc', extra=True, pattern='server/*.ini', template='template_etc', verbose=True)
    Configuration files found:
        server/group_server.ini
    Template elements found:
        group:scen2_srv
        program:scen2_config_manager
        program:scen2_check_common_data_bus
        program:scen2_common_bus_interface
        program:scen2_check_internal_data_bus
        program:scen2_internal_data_bus
        program:scen2_data_processing
        program:scen2_sensor_acquisition
    New File: server/group_scen2_srv_01.ini
    New [group:scen2_srv_01]
        programs=scen2_config_manager_01,scen2_common_bus_interface_01,scen2_check_common_data_bus_01,scen2_check_internal_data_bus_01,scen2_internal_data_bus_01,scen2_data_processing_01,scen2_sensor_acquisition_01
    New File: server/group_scen2_srv_02.ini
    New [group:scen2_srv_02]
        programs=scen2_config_manager_02,scen2_common_bus_interface_02,scen2_check_common_data_bus_02,scen2_check_internal_data_bus_02,scen2_internal_data_bus_02,scen2_data_processing_02,scen2_sensor_acquisition_02
    New File: server/group_scen2_srv_03.ini
    New [group:scen2_srv_03]
        programs=scen2_config_manager_03,scen2_common_bus_interface_03,scen2_check_common_data_bus_03,scen2_check_internal_data_bus_03,scen2_internal_data_bus_03,scen2_data_processing_03,scen2_sensor_acquisition_03
    Empty sections for file: server/group_server.ini
    Writing file: etc/server/group_scen2_srv_01.ini
    Writing file: etc/server/group_scen2_srv_02.ini
    Writing file: etc/server/group_scen2_srv_03.ini

    [bash] > supvisors_breed -d etc -t template_etc -p console/*ini -b scen2_hci=3 -x -v
    ArgumentParser: Namespace(breed={'scen2_hci': 3}, destination='etc', extra=True, pattern='console/*ini', template='template_etc', verbose=True)
    Configuration files found:
        console/group_hci.ini
    Template elements found:
        group:scen2_hci
        program:scen2_chart_view
        program:scen2_sensor_control
        program:scen2_sensor_view
        program:scen2_check_internal_data_bus
        program:scen2_internal_data_bus
    New File: console/group_scen2_hci_01.ini
    New [group:scen2_hci_01]
        programs=scen2_chart_view_01,scen2_sensor_control_01,scen2_sensor_view_01,scen2_check_internal_data_bus_01,scen2_internal_data_bus_01
    New File: console/group_scen2_hci_02.ini
    New [group:scen2_hci_02]
        programs=scen2_chart_view_02,scen2_sensor_control_02,scen2_sensor_view_02,scen2_check_internal_data_bus_02,scen2_internal_data_bus_02
    New File: console/group_scen2_hci_03.ini
    New [group:scen2_hci_03]
        programs=scen2_chart_view_03,scen2_sensor_control_03,scen2_sensor_view_03,scen2_check_internal_data_bus_03,scen2_internal_data_bus_03
    Empty sections for file: console/group_hci.ini
    Writing file: etc/console/group_scen2_hci_01.ini
    Writing file: etc/console/group_scen2_hci_02.ini
    Writing file: etc/console/group_scen2_hci_03.ini

.. attention::

    The program definitions :program:`scen2_internal_data_bus` and :program:`scen2_internal_check_data_bus` are common
    to :program:`scen2_srv` and :program:`scen2_hci`. In the use case design, it doesn't matter as
    :program:`supervisord` is not meant to include these definitions together. Anyway, it would have failed as there
    would be a conflict in loading the same program definition in two groups.

    The same problem applies to :program:`supvisors_breed`. Processing both applications together using
    :command:`supvisors_breed ... -b scen2_srv=3 scen2_hci=3` would result in an inappropriate configuration as the
    second program definition would overwrite the first one.

.. note:: *About the choice to prefix all program names with ``scen2_``*

    These programs are all included in a |supervisor| group named ``scen2``. It may indeed seem useless to do that.
    Actually the program names are quite generic and at some point the intention is to group all the applications of the
    different use cases into an unique |Supvisors| configuration. As |Supervisor| will not work with identical program
    names, even if assigned to different groups, adding ``scen2`` at this point is just to avoid future conflicts.

The resulting file tree is as follows.

.. code-block:: bash

    [bash] > tree
    .
    ├── bin
    │         ├── check_common_data_bus.sh
    │         ├── check_internal_data_bus.sh
    │         ├── common_bus_interface.sh
    │         ├── common.sh
    │         ├── config_manager.sh
    │         ├── data_processing.sh
    │         ├── internal_data_bus.sh
    │         ├── sensor_acquisition.sh
    │         ├── sensor_control.sh
    │         └── sensor_view.sh
    ├── etc
    │         ├── common
    │         │         └── group_services.ini
    │         ├── console
    │         │         ├── group_scen2_hci_01.ini
    │         │         ├── group_scen2_hci_02.ini
    │         │         └── group_scen2_hci_03.ini
    │         ├── server
    │         │         ├── group_scen2_srv_01.ini
    │         │         ├── group_scen2_srv_02.ini
    │         │         └── group_scen2_srv_03.ini
    │         ├── supervisord_console.conf
    │         └── supervisord_server.conf
    └── template_etc
        ├── console
        │         └── group_hci.ini
        └── server
            └── group_server.ini

.. note::

    As a definition, let's say that the combination of :program:`scen2_srv_01` and :program:`scen2_hci_01` is the
    :program:`Scenario 2` application that controls the item 01.

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

Now let's have a look at the console side.
Like for the server configuration, all :program:`scen2_hci` must be available on all consoles to satisfy |Req 22 abbr|.
Per definition, choosing one of the :program:`scen2_hci` is a way to choose the item to control.

|Req 20 abbr|, |Req 21 abbr| and |Req 27 abbr| are simply met using :program:`supervisorctl` commands.

.. code-block:: bash

    [bash] > supervisorctl start scen2_hci_01:*
    [bash] > supervisorctl stop scen2_hci_01:*

It is possible to do that from the |Supervisor| Web UI too, one program at a time, although it would be a bit clumsy
and a source of mistakes that would break |Req 2 abbr|.

However, there's nothing to prevent another user to start the same :program:`scen2_hci` on his console, as required in
|Req 23 abbr|.

All the other requirements are about operational status, staged start sequence and automatic behaviour and there's no
|Supervisor| function for that. It would require dedicated software development to satisfy them.
Or |Supvisors| may be used, which is the point of the next section.


Involving |Supvisors|
---------------------

When involving |Supvisors|, all :program:`Scenario 2` programs are configured using ``autostart=false``.
Only the common data bus - that is outside of the application scope - will be auto-started.

The |Supvisors| configuration is built over the |Supervisor| configuration defined above.

Rules file
~~~~~~~~~~

All the requirements about automatic behaviour are dealt within the |Supvisors| rules file. This section will detail
step by step how it is built against the requirements.

First, as all :program:`scen2_srv` instances have the same rules, a single application entry with a matching pattern is
used for all of them. The same idea applies to :program:`scen2_hci`.
Declaring these applications in the |Supvisors| rules file makes them all *Managed* in |Supvisors|, which gives control
over the X instances of the :program:`Scenario 2` application, as required in |Req 1 abbr|.

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

So far, all applications can be started on any node. Let's compel :program:`scen2_hci` to consoles and
:program:`scen2_srv` to servers, which satisfies |Req 10 abbr| and contributes to some console-related requirements.
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

It's time to introduce the staged start sequences. |Req 11 abbr| asks for an automatic start of :program:`scen2_srv`, so
a strictly positive ``start_sequence`` is added to the application configuration.

Because of |Req 4 abbr|, :program:`scen2_srv` and :program:`scen2_hci` applications will be started in three phases:

    * first the :program:`scen2_internal_data_bus_X` program,
    * then the :program:`scen2_check_internal_data_bus_X` whose job is to periodically check the
      :program:`scen2_internal_data_bus_X` status and exit when it is operational,
    * other programs.

:program:`scen2_internal_data_bus_X` and :program:`scen2_check_internal_data_bus_X` are common to :program:`scen2_srv`
and :program:`scen2_hci` and follow the same rules so it makes sense to define a common model for them.

Due to |Req 17 abbr|, two additional phases are needed for :program:`scen2_srv`:

    * the :program:`scen2_check_common_data_bus_X` whose job is to periodically check the :program:`common_data_bus`
      status and exit when it is operational,
    * finally the :program:`scen2_common_bus_interface_X`.

They are set at the end of the starting sequence so that the core of the :program:`scen2_srv` application can be
operational as a standalone application, even if it's not connected to other possible applications in the system.

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
            <program pattern="check_common">
                <reference>check_data_bus</reference>
                <start_sequence>3</start_sequence>
            </program>
            <pattern name="">
                <reference>model_services</reference>
            </pattern>
            <program pattern="check_internal_data_bus">
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
            <program pattern="check_internal_data_bus">
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

    That's why the pattern related to :program:`scen2_check_internal_data_bus_X` programs is that long. It may be argued
    that a ``check`` pattern would have been enough as it is the only program having the word 'check' in its name but
    actually the pattern ``internal_data_bus`` is a better match than the pattern ``check``, as it is more specific.

Let's now introduce the automatic behaviors.

|Req 5 abbr| implies to check the resources available before allowing an application or a program to be started.
|Supvisors| has been designed to consider the resources needed by the program over the resources actually taken.
To achieve that, the ``expected_loading`` elements of the programs have been set (quite arbitrarily for the example).

The ``starting_strategy`` element of the :program:`scen2_srv` application is set to ``LESS_LOADED`` to satisfy
|Req 13 abbr|. Before |Supvisors| starts an application or a program, it relies on the ``expected_loading`` set just
before to:

    * evaluate the current load on all nodes (due to processes already running),
    * choose the node having the lowest load and that can accept the additional load required by the program
      or application to start.

If none found, the application or the program is not started, which satisfies |Req 5 abbr|.

The ``starting_strategy`` element of the :program:`scen2_hci` application is set to ``LOCAL`` to satisfy |Req 21 abbr|.
Actually this value is only used as a default parameter in the :ref:`dashboard_application` of the |Supvisors| Web UI
and can be overridden.

In the same vein, the ``starting_failure_strategy`` element of the :program:`scen2_srv` application is set to
``STOP_APPLICATION`` (|Req 14 abbr|) and the ``starting_failure_strategy`` element of the :program:`scen2_hci`
application is set to ``CONTINUE`` (|Req 24 abbr|).

Finally, there is automatic behavior to be set on the :program:`scen2_internal_data_bus_X` programs.
The ``running_failure_strategy`` element of the ``internal_data_bus`` pattern is set to:

    * ``RESTART_APPLICATION`` for :program:`scen2_srv` applications (|Req 15 abbr|),
    * ``STOP_APPLICATION`` for :program:`scen2_hci` applications (|Req 25 abbr|),

A last impact on the rules file is about the application operational status (|Req 3 abbr|). Setting the ``required``
element on the program definitions will discriminate between major and minor failures for the applications. |Supvisors|
will provide a separate operational status for :program:`scen2_srv` and :program:`scen2_hci`. It is still the user's
responsibility to merge the status of :program:`scen2_srv_N` and :program:`scen2_hci_N` to get a global status for the
:program:`Scenario 2` application controlling the Nth item.

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
            <program pattern="check_common">
                <reference>check_data_bus</reference>
                <start_sequence>3</start_sequence>
            </program>
            <pattern name="">
                <reference>model_services</reference>
            </pattern>
            <program pattern="check_internal_data_bus">
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
            <program pattern="check_internal_data_bus">
                <reference>check_data_bus</reference>
            </program>
            <program pattern="internal_data_bus">
                <reference>data_bus</reference>
                <running_failure_strategy>STOP_APPLICATION</running_failure_strategy>
            </program>
        </application>

    </root>

Two last requirements to discuss. Actually they're already met by the combination of others.

|Req 16 abbr| aks for a restart of :program:`scen2_srv` on another server if the server it is running on is shut down or
crashes. Due to the non-distributed status of this application, all its processes will be declared ``FATAL`` in
|Supvisors| for such an event and the application will be declared stopped. The ``RESTART_APPLICATION`` set to the
:program:`scen2_internal_data_bus` program (|Req 15 abbr|) will then take over and restart the application on another
server, using the starting strategy ``LESS_LOADED`` set to the :program:`scen2_srv` application (|Req 13 abbr|) and in
accordance with the resources available (|Req 5 abbr|).

On the same principle, the running failure strategy applied to the :program:`scen2_internal_data_bus` program of the
:program:`scen2_hci` application is ``STOP_APPLICATION``. In the event of a console shutdown or crash, the
:program:`scen2_hci` will already be declared stopped, so nothing more to do and |Req 26 abbr| is therefore satisfied.


Control & Status
~~~~~~~~~~~~~~~~

The operational status of :program:`Scenario 2` required by the |Req 3 abbr| is made available through:

    * the :ref:`dashboard_application` of the |Supvisors| Web UI, as a LED near the application state,
    * the :ref:`xml_rpc` (example below),
    * the :ref:`extended_status` of the extended :program:`supervisorctl` or :program:`supvisorsctl` (example below),
    * the :ref:`event_interface`.

For the examples, the following context applies:

    * only 3 nodes among the 8 defined are running: 2 servers (``cliche81`` and ``cliche82``) and one console
      (``cliche83``) - clearly due to limited testing resources ;
    * :program:`common_data_bus` is *Unmanaged* so |Supvisors| always considers this 'application' as ``STOPPED``
      (the process status is yet ``RUNNING``) ;
    * :program:`scen2_srv_01` and :program:`scen2_srv_03` are running on the server ``cliche81`` ;
    * :program:`scen2_srv_02` is running on the server ``cliche82`` ;
    * :program:`scen2_hci_02` has been started on the console ``cliche83`` ;
    * an attempt to start :program:`scen2_hci_03` on the server ``cliche81`` has been rejected.

>>> from supervisor.childutils import getRPCInterface
>>> proxy = getRPCInterface({'SUPERVISOR_SERVER_URL': 'http://localhost:61000'})
>>> proxy.supvisors.get_all_applications_info()
[{'application_name': 'common_data_bus', 'statecode': 0, 'statename': 'STOPPED', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen2_srv_01', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen2_srv_02', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen2_srv_03', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen2_hci_01', 'statecode': 0, 'statename': 'STOPPED', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen2_hci_02', 'statecode': 2, 'statename': 'RUNNING', 'major_failure': False, 'minor_failure': False},
{'application_name': 'scen2_hci_03', 'statecode': 0, 'statename': 'STOPPED', 'major_failure': True, 'minor_failure': True}]

.. code-block:: bash

    [bash] > supvisorsctl -s http://localhost:61000 application_info
    Application      State     Major  Minor
    common_data_bus  STOPPED   False  False
    scen2_srv_01     RUNNING   False  False
    scen2_srv_02     RUNNING   False  False
    scen2_srv_03     RUNNING   False  False
    scen2_hci_01     STOPPED   False  False
    scen2_hci_02     RUNNING   False  False
    scen2_hci_03     STOPPED   True   True

To start a :program:`scen2_hci` in accordance with |Req 20 abbr|, |Req 21 abbr| and |Req 22 abbr|, the following methods
are available:

    * the :ref:`xml_rpc` (example below - **beware of the target**),
    * the :ref:`application_control` of the extended :program:`supervisorctl` or :program:`supvisorsctl` (examples
      below):

        - using the configuration file **if executed from the targeted console**,
        - using the URL otherwise,

    * the start button |start| at the top right of the :ref:`dashboard_application` of the |Supvisors| Web UI,
      **assuming that the user has navigated to this page using the relevant node** (check the url if necessary).


>>> from supervisor.childutils import getRPCInterface
>>> proxy = getRPCInterface({'SUPERVISOR_SERVER_URL': 'http://localhost:61000'})
>>> proxy.supvisors.start_application('LOCAL', 'scen2_hci_02')
True

If the XML-RPC has to be performed from a remote node, the |Supvisors| ``getRPCInterface`` can be used as the
|Supervisor| function does not provide a parameter to address a remote node.

>>> from supvisors.rpcrequests import getRPCInterface
>>> proxy = getRPCInterface('cliche83', {'SUPERVISOR_SERVER_URL': 'http://localhost:61000'})
>>> proxy.supvisors.start_application('LOCAL', 'scen2_hci_02')
True

.. code-block:: bash

    [bash] > hostname
    cliche83
    [bash] > supervisorctl -c etc/supervisord_console.conf start_application LOCAL scen2_hci_02
    scen2_hci_02 started

    [bash] > hostname
    cliche81
    [bash] > supvisorsctl -s http://cliche83:61000 start_application LOCAL scen2_hci_02
    scen2_hci_02 started

.. hint::

    |Supervisor|'s :program:`supervisorctl` does not provide support for extended API using the ``-s URL`` option.
    But |Supvisors|' :program:`supvisorsctl` does.

|Req 12 abbr| and |Req 23 abbr| require that one instance of one instance of :program:`scen2_srv_N` and
:program:`scen2_hci_N` are running at most. This is all managed by |Supvisors| as they are *Managed* applications.
If the :program:`scen2_srv_N` is already running on a console, the |Supvisors| Web UI will prevent the user to start
:program:`scen2_srv_N` from another console. |Supvisors| XML-RPC and extended :program:`supervisorctl` commands will be
rejected.

.. attention::

    The |Supervisor| commands (XML-RPC or :program:`supervisorctl`) are NOT curbed in any way by |Supvisors| so it is
    still possible to break the rule using |Supervisor| itself. In the event of multiple :program:`Scenario 2` programs running,
    |Supvisors| will detect the conflicts and enter a ``CONCILIATION`` state. Please refer to :ref:`conciliation` for
    more details.

To stop a :program:`scen2_hci` (|Req 27 abbr|), the following methods are available:

    * the :ref:`xml_rpc` (example below - **whatever the target**),
    * the :ref:`application_control` of the extended :program:`supervisorctl` or :program:`supvisorsctl` **from any
      node where |Supvisors| is running** (example below),
    * the stop button |stop| at the top right of the :ref:`dashboard_application` of the |Supvisors| Web UI,
      **whatever the node hosting this page**.

Indeed, as |Supvisors| knows where the application is running, it is able to drive the application stop from anywhere.

>>> from supvisors.rpcrequests import getRPCInterface
>>> proxy = getRPCInterface('localhost', {'SUPERVISOR_SERVER_URL': 'http://:61000'})
>>> proxy.supvisors.stop_application('scen2_hci_02')
True

.. code-block:: bash

    [bash] > hostname
    cliche81
    [bash] > supervisorctl -c etc/supervisord_server.conf stop_application scen2_hci_02
    scen2_hci_02 stopped

.. image:: images/supvisors_scenario_2.png
    :alt: Supvisors Use Cases - Scenario 2
    :align: center

As a conclusion, all the requirements are met using |Supvisors| and without any impact on the application to be
supervised. |Supvisors| improves application control and status.


Example
-------

The full example is available in `Supvisors Use Cases - Scenario 2 <https://github.com/julien6387/supvisors/tree/master/supvisors/test/use_cases/scenario_2>`_.

An additional configuration for a single node and with automatic start of a HCI is also provided:

    * etc/supervisord_localhost.conf
    * etc/supvisors_localhost_rules.xml

.. include:: common.rst
