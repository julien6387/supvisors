# **Supvisors**
[![PyPI version][pypi-image]][pypi-url]
[![Python Versions][pypi-python-versions]][pypi-url]
[![License][license-image]][license-url]
[![Build Status][ci-image]][ci-url]
[![Coverage Status][coveralls-image]][coveralls-url]
[![Documentation Status][docs-image]][docs-url]
[![Downloads][downloads-image]][downloads-url]


**Supvisors** is a Control System for Distributed Applications, based on multiple instances of Supervisor
running over multiple nodes.

**Supvisors** works as a Supervisor plugin and its main features are:
* a new web-based dashboard that replaces the default dashboard of Supervisor and allows to control
  all the Supervisor instances declared,
* an extended XML-RPC API to control applications and processes over the multiple Supervisor instances,
* a notification interface to get the events from multiple Supervisor instances on a `websocket` or on a `PyZmq` socket.

A set of application and program rules can be added to manage:
* the starting sequence of the applications,
* the stopping sequence of the applications,
* the starting strategy of the processes,
* the strategy to apply when a process crashes or when a node shuts down,
* the strategy to apply when conflicts are detected.

The Supervisor program `supervisorctl` has been extended to include the additional XML-RPC API.

Also provided in the scope of this project:
* a `JAVA` client with a full implementation of the Supervisor and **Supvisors** XML-RPC API ;
* a `Flask-RESTX` application that exposes the Supervisor and **Supvisors** XML-RPC API through a REST API.

![Image of Supvisors' Dashboard](https://github.com/julien6387/supvisors/blob/master/docs/images/supvisors_address_process_section.png)

## Supervisor Enhancements

**Supvisors** proposes a contribution to the following Supervisor issues:
* [#122 - supervisord Starts All Processes at the Same Time](https://github.com/Supervisor/supervisor/issues/122)
* [#177 - Dynamic numproc change](https://github.com/Supervisor/supervisor/issues/177)
* [#456 - Add the ability to set different "restart policies" on process workers](https://github.com/Supervisor/supervisor/issues/456)
* [#520 - allow a program to wait for another to stop before being stopped?](https://github.com/Supervisor/supervisor/issues/520)
* [#591 - New Feature: disable/enable](https://github.com/Supervisor/supervisor/issues/591)
* [#712 - shutdown supervisord once one of the programs is killed](https://github.com/Supervisor/supervisor/issues/712)
* [#723 - Restart waits for all processes to stop before starting any](https://github.com/Supervisor/supervisor/issues/723)
* [#763 - unexpected exit not easy to read in status or getProcessInfo](https://github.com/Supervisor/supervisor/issues/763)
* [#874 - Bring down one process when other process gets killed in a group](https://github.com/Supervisor/supervisor/issues/874)
* [#1023 - Pass arguments to program when starting a job?](https://github.com/Supervisor/supervisor/issues/1023)
* [#1150 - Why do event listeners not report the process exit status when stopped/crashed?](https://github.com/Supervisor/supervisor/issues/1150)
* [#1455 - using supervisorctl with -s does not provide access to the extended API](https://github.com/Supervisor/supervisor/issues/1455)
* [#1504 - Web interface: Add stop group Action](https://github.com/Supervisor/supervisor/issues/1504)


## Supported Platforms

**Supvisors** has been tested and is known to run on Linux (Rocky 8, RedHat 8, Ubuntu 20 to 24).
It will likely work fine on most UNIX systems.

**Supvisors** will not run at all under any version of Windows.

From the version 0.19, **Supvisors** works with `Python 3.9` to `Python 3.12`.

Due to the lack of support of `Python 3.6` and `Python 3.7` in the Ubuntu releases provided in the Standard
GitHub-hosted runners, **Supvisors** is now based on the minimal `Python` release provided in RedHat 9,
i.e., `Python 3.9`.

**Supvisors** 0.18.7 is therefore the last version supporting `Python 3.6` to `Python 3.8`.

## Dependencies

**Supvisors** has dependencies on:

| Package                                            | Optional | Minimal release |
|----------------------------------------------------|----------|-----------------|
| [Supervisor](http://supervisord.org)               |          | 4.2.4           |
| [psutil](https://pypi.python.org/pypi/psutil)      | X        | 5.9.0           |
| [matplotlib](http://matplotlib.org)                | X        | 3.5.1           |
| [lxml](http://lxml.de)                             | X        | 4.8.0           |
| [Flask-RESTX](https://flask-restx.readthedocs.io)  | X        | 1.2.0           |
| [PyZMQ](http://pyzmq.readthedocs.io)               | X        | 25.1.1          |
| [websockets](https://websockets.readthedocs.io)    | X        | 11.0.3          |

Please note that some of these dependencies may have their own dependencies.

Versions are given for information.
Although **Supvisors** has been developed and tested with these releases, the minimal release of each dependency
is unknown. Other releases are likely working as well.


## Installation

Supvisors can be installed with `pip install`:

```bash
   # minimal install (including only Supervisor and its dependencies)
   [bash] > pip install supvisors

   # extra install for all optional dependencies
   [bash] > pip install supvisors[all]
```

## Documentation

You can view the current **Supvisors** documentation on [Read the Docs](http://supvisors.readthedocs.io).

You will find detailed installation and configuration documentation.

## Reporting Bugs and Viewing the Source Repository

Please report bugs in the [GitHub issue tracker](https://github.com/julien6387/supvisors/issues).

You can view the [source repository](https://github.com/julien6387/supvisors) for Supvisors.

## Contributing

Not opened yet.

[pypi-image]: https://badge.fury.io/py/supvisors.svg
[pypi-python-versions]: https://img.shields.io/pypi/pyversions/supvisors.svg
[pypi-url]: https://badge.fury.io/py/supvisors

[license-image]: https://img.shields.io/badge/License-Apache_2.0-blue.svg
[license-url]: https://opensource.org/licenses/Apache-2.0

[ci-image]: https://github.com/julien6387/supvisors/actions/workflows/ci.yml/badge.svg?branch=master
[ci-url]: https://github.com/julien6387/supvisors/actions/workflows/ci.yml

[coveralls-image]: https://coveralls.io/repos/github/julien6387/supvisors/badge.svg?branch=master
[coveralls-url]: https://coveralls.io/github/julien6387/supvisors?branch=master

[docs-image]: https://readthedocs.org/projects/supvisors/badge/?version=master
[docs-url]: https://supvisors.readthedocs.io/en/master

[downloads-image]: https://static.pepy.tech/badge/supvisors/month
[downloads-url]: https://pepy.tech/project/supvisors
