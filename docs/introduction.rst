.. _introduction:

Introduction
============

Overview
--------

|Supvisors| is a control system for distributed applications over multiple |Supervisor| instances.

The |Supvisors| software is born from a common need in embedded systems where applications are distributed over several
nodes. The problematic comes with the following challenges:

    * to have a status of the processes,
    * to have a synthetic status of the applications based on the processes status,
    * to have basic statistics about the resources taken by the applications,
    * to have a basic status of the nodes,
    * to control applications and processes dynamically,
    * to distribute the same application over different platforms (developer machine, integration platform, etc),
    * to deal with resources (CPU, memory, network, etc),
    * to deal with failures:

        + missing node when starting,
        + crash of a process,
        + crash of a node.

As a bonus:

    * it should be free, open source, not subject to export control issues,
    * it shouldn't require specific administration rights (root).

|Supervisor| can handle a part of the requirements but it only works on a single UNIX-like operating system.
The |Supervisor| website references some `third parties <http://supervisord.org/plugins.html>`_
dealing with multiple |Supervisor| instances but they only consist in dashboards and they focus on the nodes rather
than on the applications and their possible distribution over nodes.
Nevertheless, the extensibility of |Supervisor| makes it possible to implement the missing requirements.

|Supvisors| works as a |Supervisor| plugin and is intended for those who are already familiar with |Supervisor| or
who have neither the time nor the resources to invest in a complex orchestration tool like Kubernetes.


Definitions
-----------

Here follows a few definitions of terms are used throughout the present documentation.

    The term *Node* refers to an UNIX operating system having a dedicated host name and IP address.

    A |Supervisor| *instance* is a |Supervisor| damon running on a *Node*, and with a distinct HTTP configuration.

    A |Supvisors| *instance* refers to a |Supervisor| *instance* including a |Supvisors| extension.

    |Supvisors| corresponds to the distributed software grouping all the |Supvisors| *instances* configured to work
    together.

    Multiple |Supvisors| *instances* running on the same *Node* do not necessarily belong to the same |Supvisors|.

    A |Supervisor| *Process* is a structure whose configuration is described in a |Supervisor| *Program*
    (or *Homogeneous Process Group*). It is managed by a single |Supervisor| *instance*. |br|
    This |Supervisor| *instance* is able to spawn a UNIX process based on this structure and to control it.

    A |Supervisor| *Group* (or *Heterogeneous Process Group*) is a collection of |Supervisor| *Programs*.
    It is also managed by a single |Supervisor| *instance*.

    A |Supvisors| *Process* is the union of all |Supervisor| *Processes* sharing the name |Supervisor| *Group* name
    and *Process* name within |Supvisors|. |br|
    Such a |Supervisor| *Process* is not necessarily defined in all |Supervisor| *instances*.

    A |Supvisors| *Application* is the collection of all |Supvisors| *Processes* sharing the name |Supervisor| *Group*
    name within |Supvisors|.

    The definitions of all |Supvisors| *Processes* and |Supvisors| *Applications* are shared across |Supvisors| and
    all |Supvisors| *instances* have control over them, even if the process definition is unknown to their respective
    hosting |Supervisor| *instance*.


Platform Requirements
---------------------

|Supvisors| has been tested and is known to run on Linux (Rocky 8.5, RedHat 8.2 and Ubuntu 20.04 LTS).

|Supvisors| will not run at all under any version of Windows.

|Supvisors| works with :command:`Python 3.6` to :command:`Python 3.12`.

An old release of |Supvisors| (version 0.1, available on PyPi) works with :command:`Python 2.7` (and previous
versions of |Supervisor|, i.e. 3.3.0) but is not maintained anymore.

The CSS of the Dashboard has been written for Firefox ESR 91.3.0.
The compatibility with other browsers or other versions of Firefox is unknown.


Installation
------------

|Supvisors| has the following dependencies:

+----------------+--------------------+------------------------------------------------------------------------------------+
| Package        | Minimal release    | Usage                                                                              |
+================+====================+====================================================================================+
| |Supervisor|   | 4.2.4              | Base software, extended by |Supvisors|                                             |
+----------------+--------------------+------------------------------------------------------------------------------------+
| |psutil|       | 5.7.3              | *(optional)* Information about system usage                                        |
+----------------+--------------------+------------------------------------------------------------------------------------+
| matplotlib_    | 3.3.3              | *(optional)* Graphs for Dashboard                                                  |
+----------------+--------------------+------------------------------------------------------------------------------------+
| |lxml|         | 4.6.2              | *(optional)* XSD validation of the XML rules file                                  |
+----------------+--------------------+------------------------------------------------------------------------------------+
| |Flask-RESTX|  | 0.5.1 (py36) |br|  | *(optional)* Expose the Supervisor and Supvisors XML-RPC API through a REST API    |
|                | 1.1.0 (py37+)      |                                                                                    |
+----------------+--------------------+------------------------------------------------------------------------------------+
| |PyZMQ|        | 25.1.1             | *(optional)* Alternative for the Supvisors Event interface                         |
+----------------+--------------------+------------------------------------------------------------------------------------+
| |Websockets|   | 10.4               | *(optional)* Alternative for the Supvisors Event interface (requires Python 3.7+)  |
+----------------+--------------------+------------------------------------------------------------------------------------+

With an Internet access
~~~~~~~~~~~~~~~~~~~~~~~

Supvisors can be installed with ``pip install``:

.. code-block:: bash

   # minimal install (including Supervisor)
   [bash] > pip install supvisors

   # install including all optional dependencies
   [bash] > pip install supvisors[all]

   # install for dashboard statistics and graphs only
   # (includes psutil and matplotlib)
   [bash] > pip install supvisors[statistics]

   # install for XML validation only (includes lxml)
   [bash] > pip install supvisors[xml_valid]

   # install for the REST API (includes flask-restx)
   [bash] > pip install supvisors[flask]

   # install for the ZMQ event interface (includes PyZMQ)
   [bash] > pip install supvisors[zmq]

   # install for the Websockets event interface (includes websockets, requires Python 3.7+)
   [bash] > pip install supvisors[ws]

Without an Internet access
~~~~~~~~~~~~~~~~~~~~~~~~~~

All the dependencies have to be installed prior to |Supvisors|.
Refer to the documentation of these dependencies.

Finally, get the latest release from `Supvisors releases <https://github.com/julien6387/supvisors/releases>`_,
unzip the archive and enter the directory :command:`supvisors-{version}`.

Install |Supvisors| with the following command:

.. code-block:: bash

   [bash] > python setup.py install

Additional commands
~~~~~~~~~~~~~~~~~~~

During the installation, a few additional commands are added to the ``BINDIR`` (directory that the :command:`Python`
installation has been configured with):

    * :command:`supvisorsctl` provides access to the extended **Supvisors** API when used with the option ``-s URL``,
      which is missed from the |Supervisor| :command:`supervisorctl` (refer to the :ref:`extended_supervisorctl` part).
    * :command:`supvisorsflask` provides a |Flask-RESTX| application that exposes the |Supervisor| and |Supvisors|
      XML-RPC APIs through a REST API (refer to the :ref:`rest_api` page).

.. attention::

    :command:`supvisorsflask` uses the |Flask|'s built-in server, which should not be an issue as it is unlikely
    that this interface ever needs to be scaled.


Running |Supvisors|
-------------------

|Supvisors| runs as a plugin of |Supervisor| so it follows the same principle as
`Running Supervisor <http://supervisord.org/running.html>`_ but using multiple UNIX-like operating systems.

Although |Supvisors| was originally designed to handle exactly one |Supervisor| instance per node, it can handle
multiple |Supervisor| instances on each node since the version 0.11.

However, the |Supervisor| configuration file **MUST**:

    * be configured with an internet socket (refer to the
      `inet-http-server <http://supervisord.org/configuration.html#inet-http-server-section-settings>`_
      section settings) ;
    * include the ``[rpcinterface:supvisors]`` and the ``[ctlplugin:supvisors]`` sections
      (refer to the :ref:`configuration` page) ;
    * be consistent on all considered nodes, more particularly attention must be paid to the list of declared
      |Supvisors| instances and the IP ports used.

.. important::

    A script may be required to start |Supervisor| on several nodes if not configured to run automatically at
    startup (:command:`ssh` loop for example).


.. include:: common.rst
