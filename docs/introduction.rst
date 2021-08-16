Introduction
============

Overview
--------

**Supvisors** is a control system for distributed applications over multiple Supervisor_ instances.

This piece of software was born from a common need in embedded systems where applications are distributed over several
nodes.

This problematic comes with the following challenges:

    * have a detailed status of the applications,
    * have basic statistics about the resources taken by the applications,
    * have a basic status of the nodes,
    * start / stop processes dynamically,
    * distribute the same application over different platforms,
    * control the applications from nodes outside of the platform,
    * secure the control / status interfaces,
    * deal with loading (CPU, memory, etc),
    * deal with failures:

        + missing node when starting,
        + crash of a process,
        + crash of a node.

As a bonus:

    * it should be free, open source, without export control,
    * it shouldn't require specific administration rights (root).

After some researches on the net - at the time -, it seemed that there was no simple, free and open source solution
meeting all these requirements. Of course, there are now orchestration solutions like Kubernetes, Docker Swarm, Mesos,
etc. coming with more or less complexity, some working on containers only.

Supervisor_ can handle a part of the requirements but it only works on a single UNIX-like operating system.
The Supervisor website references some `third parties <http://supervisord.org/plugins.html>`_
that deal with multiple Supervisor instances but they only consist in dashboards and they focus on the nodes rather than
on the applications and their possible distribution over nodes.
Nevertheless, the extensibility of Supervisor makes it possible to implement the missing requirements.

**Supvisors** works as a Supervisor plugin and is intended for those who are already familiar with Supervisor or
who have neither the time nor the resources to invest in a complex orchestration tool.

In this documentation, a *Supvisors instance* refers to a *Supervisor instance* including a **Supvisors** extension.


Platform Requirements
---------------------

**Supvisors** has been tested and is known to run on Linux (CentOS 8.3).

**Supvisors** will not run at all under any version of Windows.

**Supvisors** works with Python 3.6 or later but will not work under any version of Python 2.

A previous release of **Supvisors** (version 0.1, available on PyPi) works with Python 2.7 (and previous versions of Supervisor, i.e. 3.3.0) but is not maintained anymore.

The CSS of the Dashboard has been written for Firefox ESR 60.3.0.
The compatibility with other browsers or other versions of Firefox is unknown.


Installation
------------

**Supvisors** has the following dependencies:

+---------------+------------+-----------------------------------------------------------------+
| Package       | Release    | Usage                                                           |
+===============+============+=================================================================+
| Supervisor_   | 4.2.1      | Base software, extended by **Supvisors**                        |
+---------------+------------+-----------------------------------------------------------------+
| PyZMQ_        | 22.0.3     | Python binding of ZeroMQ                                        |
+---------------+------------+-----------------------------------------------------------------+
| psutil_       | 5.7.3      | *Information about system usage (optional)*                     |
+---------------+------------+-----------------------------------------------------------------+
| matplotlib_   | 3.3.3      | *Graphs for Dashboard (optional)*                               |
+---------------+------------+-----------------------------------------------------------------+
| lxml_         | 4.6.2      | *XSD validation of the XML rules file (optional)*               |
+---------------+------------+-----------------------------------------------------------------+

With an Internet access
~~~~~~~~~~~~~~~~~~~~~~~

Supvisors can be installed with ``pip install``:

.. code-block:: bash

   # minimal install (including Supervisor and PyZMQ)
   [bash] > pip install supvisors

   # extra install for all optional dependencies
   [bash] > pip install supvisors[all]

   # extra install for dashboard statistics and graphs only
   # (includes psutil and matplotlib)
   [bash] > pip install supvisors[statistics]

   # extra install for XML validation only (includes lxml)
   [bash] > pip install supvisors[xml_valid]

   # extra install for use of IP aliases only (includes psutil)
   [bash] > pip install supvisors[ip_address]

Without an Internet access
~~~~~~~~~~~~~~~~~~~~~~~~~~

All the dependencies have to be installed prior to **Supvisors**.
Refer to the documentation of the dependencies.

Finally, get the latest release from `Supvisors releases <https://github.com/julien6387/supvisors/releases>`_,
unzip the archive and enter the directory :command:`supvisors-version`.

Install **Supvisors** with the following command:

.. code-block:: bash

   [bash] > python setup.py install


Running **Supvisors**
---------------------

**Supvisors** runs as a plugin of Supervisor so it follows the same principle as
`Running Supervisor <http://supervisord.org/running.html>`_ but using multiple UNIX-like operating systems.

However, the Supervisor configuration file **MUST**:

    * be configured with an internet socket (refer to the `inet-http-server <http://supervisord.org/configuration.html#inet-http-server-section-settings>`_ section settings) ;
    * include the :command:`[supvisors]` section (refer to the :ref:`Configuration` part) ;
    * be identical on all considered nodes.

.. note::

    A script may be required to start Supervisor on several addresses if not configured to run automatically at startup (ssh loop for example).

    All Supervisor instances should be started during a configurable lap of time so that **Supvisors** works as expected.

.. _Supervisor: http://supervisord.org
.. _PyZMQ: http://pyzmq.readthedocs.io
.. _psutil: https://pypi.python.org/pypi/psutil
.. _matplotlib: http://matplotlib.org
.. _lxml: http://lxml.de
