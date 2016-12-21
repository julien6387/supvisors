Supervisors
===========

Supervisors is a Control System for Distributed Applications, based on multiple instances of Supervisor.

Supported Platforms
-------------------

Supervisor has been tested and is known to run on Linux (CentOS 7.2).
It will likely work fine on most UNIX systems.

Supervisors will not run at all under any version of Windows.

Supervisors is known to work with Python 2.7 or later but will not work under any version of Python 3.

Dependencies
-------------

Supervisors has dependencies on:

+ Supervisor 3.3.0
+ ZeroMQ 4.1.2
+ PyZMQ 15.2.0
+ psutil 4.3.0
+ netifaces 0.10.4
+ matplotlib 1.2.0 (optional)
+ lxml 3.2.1 (optional)

Please note that some of these dependencies may have their own dependencies.

Versions are given for information.
Although Supervisors has been developed and tested with these releases, the minimal release of each dependency is unknown.
Other releases are likely working as well.

Installation
-------------

Get the latest release from `here
<https://github.com/julien6387/supervisors/releases>`_.
Unzip the archive and enter the directory supervisors-*version*.

Install Supervisors with the following command:
    *python setup.py install*

Documentation
-------------

You can view the current Supervisors documentation in the **supervisors/doc** directory of the installation.
You will find detailed installation and configuration documentation.
For the moment, the CSS is Firefox-compliant only.

Reporting Bugs and Viewing the Source Repository
---------------------------------------------------------------

Please report bugs in the `Github issue tracker
<https://github.com/julien6387/supervisors/issues>`_.

You can view the source repository for supervisors via
`https://github.com/julien6387/supervisors
<https://github.com/julien6387/supervisors>`_.

Contributing
------------

Not opened yet.

