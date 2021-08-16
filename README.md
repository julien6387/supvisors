# **Supvisors**
[![PyPI version][pypi-image]][pypi-url] [![Build Status][ci-image]][ci-url] [![Coverage Status][coveralls-image]][coveralls-url] [![Documentation Status][docs-image]][docs-url]


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

![Image of Supvisors' Dashboard](https://github.com/julien6387/supvisors/blob/master/docs/images/supvisors_address_process_section.png)

## Supervisor Enhancements

**Supvisors** proposes a contribution to the following Supervisor issues:
   * [#122 - supervisord Starts All Processes at the Same Time](https://github.com/Supervisor/supervisor/issues/122)
   * [#456 - Add the ability to set different "restart policies" on process workers](https://github.com/Supervisor/supervisor/issues/456)
   * [#520 - allow a program to wait for another to stop before being stopped?](https://github.com/Supervisor/supervisor/issues/520)
   * [#723 - Restart waits for all processes to stop before starting any](https://github.com/Supervisor/supervisor/issues/723)
   * [#874 - Bring down one process when other process gets killed in a group](https://github.com/Supervisor/supervisor/issues/874)
   * [#1023 - Pass arguments to program when starting a job?](https://github.com/Supervisor/supervisor/issues/1023)
   * [#1150 - Why do event listeners not report the process exit status when stopped/crashed?](https://github.com/Supervisor/supervisor/issues/1150)

## Supported Platforms

**Supvisors** has been tested and is known to run on Linux (CentOS 8.3).
It will likely work fine on most UNIX systems.

**Supvisors** will not run at all under any version of Windows.

**Supvisors** >= 0.2 works with Python 3.6 or later.

**Supvisors** 0.1 (available on PyPi) works with Python 2.7 (and former versions of Supervisor, i.e. 3.3.0)
but is not maintained anymore.

## Dependencies

**Supvisors** has dependencies on:

Package                                             | Release    | Optional
----------------------------------------------------|------------|---------
[Supervisor](http://supervisord.org)                | 4.2.1      |
[PyZMQ](http://pyzmq.readthedocs.io)                | 20.0.0     |
[psutil](https://pypi.python.org/pypi/psutil)       | 5.7.3      |     X
[matplotlib](http://matplotlib.org)                 | 3.3.3      |     X
[lxml](http://lxml.de)                              | 4.6.2      |     X

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

[pypi-image]: https://badge.fury.io/py/supvisors.svg
[pypi-url]: https://badge.fury.io/py/supvisors

[ci-image]: https://travis-ci.org/julien6387/supvisors.svg?branch=master
[ci-url]: https://travis-ci.org/julien6387/supvisors?branch=master

[coveralls-image]: https://coveralls.io/repos/github/julien6387/supvisors/badge.svg?branch=master
[coveralls-url]: https://coveralls.io/github/julien6387/supvisors?branch=master

[docs-image]: https://readthedocs.org/projects/supvisors/badge/?version=master
[docs-url]: https://supvisors.readthedocs.io/en/master
