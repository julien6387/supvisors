Introduction
============

Overview
--------

**Supvisors** is a control system for distributed applications over multiple
Supervisor_ instances.

This piece of software is born from a common need in embedded systems where
applications are distributed over several boards.

This problematic comes with the following challenges:

    * have a detailed status of the application,
    * have statistics about the resources taken by the application,
    * have a basic status of the boards,
    * start / stop processes dynamically,
    * distribute the same application according to different platforms,
    * control the application from outside of the platform,
    * secure the control / status interfaces,
    * deal with loading (CPU, memory, etc),
    * deal with failures:

        + missing board when starting,
        + crash of a process,
        + crash of a board.

Icing on the cake:

    * it should be free, open source, without export control,
    * it shouldn't require specific administration rights (root).

After some researches on the net, it seems that there is no simple,
free and open source solution that meets all these requirements.
Supervisor_ can handle a part of these requirements but it only
works on a single UNIX-like operating system.

The Supervisor website references some `tools <http://supervisord.org/plugins.html>`_
that deal with multiple Supervisor instances but they only consist in dashboards
and none of them is focused on the application itself.
Nevertheless, the extensibility of Supervisor made it possible to implement the
missing requirements.

In this documentation, a *Supvisors instance* refers to a *Supervisor instance*
including a **Supvisors** extension.


Platform Requirements
---------------------

**Supvisors** has been tested and is known to run on Linux (CentOS 7.2).

**Supvisors** will not run at all under any version of Windows.

**Supvisors** works with Python 2.7 or later but will not work under any
version of Python 3.

The CSS of the Dashboard has been written for Firefox ESR 45.4.0.
The compatibility with other browsers or other versions of Firefox is unknown.


Installation
------------

**Supvisors** has the following dependencies:

+---------------+------------+-----------------------------------------------------------------+
| Package       | Release    | Usage                                                           |
+===============+============+=================================================================+
| Supervisor_   | 3.3.2      | Base software, extended by **Supvisors**                        |
+---------------+------------+-----------------------------------------------------------------+
| PyZMQ_        | 16.0.2     | Python binding of ZeroMQ                                        |
+---------------+------------+-----------------------------------------------------------------+
| psutil_       | 4.3.0      | *Information about processes and system utilization (optional)* |
+---------------+------------+-----------------------------------------------------------------+
| netifaces_    | 0.10.4     | *IPv4 aliases from host name (optional)*                        |
+---------------+------------+-----------------------------------------------------------------+
| matplotlib_   | 1.2.0      | *Graphs for Dashboard (optional)*                               |
+---------------+------------+-----------------------------------------------------------------+
| lxml_         | 3.2.1      | *XSD validation of the XML rules file (optional)*               |
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

   # extra install for use of IP aliases only (includes netifaces)
   [bash] > pip install supvisors[ip_address]

Without an Internet access
~~~~~~~~~~~~~~~~~~~~~~~~~~

All the dependencies have to be installed prior to **Supvisors**.
Refer to the documentation of the dependencies.

Finally, get the latest release from `Supvisors releases
<https://github.com/julien6387/supvisors/releases>`_,
unzip the archive and enter the directory :command:`supvisors-version`.

Install **Supvisors** with the following command:

.. code-block:: bash

   [bash] > python setup.py install


Running **Supvisors**
---------------------

**Supvisors** runs as a plugin of Supervisor so it follows the same principle as
`Running Supervisor <http://supervisord.org/running.html>`_ but using multiple
UNIX-like operating systems.

However, the Supervisor configuration file MUST:

    * be configured with an internet socket (refer to the `inet-http-server
    <http://supervisord.org/configuration.html#inet-http-server-section-settings>`_
    section settings),
    * include the :command:`[supvisors]` section (refer to the
    :ref:`Configuration` part).

.. note::

    A script may be required to start Supervisor on several addresses if not configured
    to run automatically at startup (ssh loop for example).

    All Supervisor instances should be started during a given lap of time so that
    **Supvisors** works as expected.

.. _Supervisor: http://supervisord.org
.. _PyZMQ: http://pyzmq.readthedocs.io
.. _psutil: https://pypi.python.org/pypi/psutil
.. _netifaces: https://pypi.python.org/pypi/netifaces
.. _matplotlib: http://matplotlib.org
.. _lxml: http://lxml.de
