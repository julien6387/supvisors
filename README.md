# **Supvisors**

**Supvisors** is a Control System for Distributed Applications, based on
multiple instances of Supervisor.

The main features are:
   * a new web-based dashboard that replaces the default dashboard of Supervisor,
   * an extended XML-RPC API to control applications and multiple Supervisor instances,
   * the definition of a rules file to handle:
      * the starting sequence of the applications,
      * the stopping sequence of the applications,
      * the starting strategy of the processes,
      * the strategy to apply when a process crashes.

![Image of Supvisors' Dashboard](https://github.com/julien6387/supvisors/blob/master/docs/images/supvisors_address_host_section.png)


## Supported Platforms

**Supvisors** has been tested and is known to run on Linux (CentOS 8.3).
It will likely work fine on most UNIX systems.

**Supvisors** will not run at all under any version of Windows.

**Supvisors** >= 0.2 works with Python 3.6 or later.

**Supvisors** 0.1 (available on PyPi) works with Python 2.7 (and former versions of Supervisor, i.e. 3.3.0)
but is not maintained anymore.

[![Build Status](https://travis-ci.org/julien6387/supvisors.svg?branch=master)](https://travis-ci.org/julien6387/supvisors)

## Dependencies

**Supvisors** has dependencies on:

Package    | Release    | Optional
-----------|------------|---------
Supervisor | 4.2.1      |
PyZMQ      | 20.0.0     |
psutil     | 5.7.3      |     X
netifaces  | 0.10.9     |     X
matplotlib | 3.3.3      |     X
lxml       | 4.6.2      |     X


Please note that some of these dependencies may have their own dependencies.

Versions are given for information.
Although **Supvisors** has been developed and tested with these releases,
the minimal release of each dependency is unknown.
Other releases are likely working as well.


## Installation

Supvisors can be installed with `pip install`:

```bash
   # minimal install (including Supervisor and PyZMQ)
   [bash] > pip install supvisors

   # extra install for all optional dependencies
   [bash] > pip install supvisors[all]
```

## Documentation

You can view the current **Supvisors** documentation [here](http://supvisors.readthedocs.io).

You will find detailed installation and configuration documentation.


## Reporting Bugs and Viewing the Source Repository

Please report bugs in the [Github issue tracker](https://github.com/julien6387/supvisors/issues).

You can view the [source repository](https://github.com/julien6387/supvisors) for Supvisors.

## Contributing

Not opened yet.

