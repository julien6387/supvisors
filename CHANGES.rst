Change Log
==========

0.7 (2021-xx-xx)
----------------

* Starting strategy added to the application rules.

* Documentation updated.


0.6 (2021-08-01)
----------------

* Improve **Supvisors** stability when dealing with remote programs undefined locally.

* Add expand / shrink actions to applications to the ``ProcAddressView`` of the Web UI.

* Upon authorization of a new node in **Supvisors**, back to ``DEPLOYMENT`` state to repair applications.

* Add RPC ``change_log_level`` to dynamically change the **Supvisors** log level.

* Application state is evaluated only against the starting sequence of its processes.

* Fixed blocking when *Master* is stopped while in ``DEPLOYMENT`` state.

* Fixed issue with applications that would not fully stop when using the ``STOP_APPLICATION`` starting failure strategy.

* Fixed issue related to `Issue #85 <https://github.com/julien6387/supvisors/issues/85>`_.
  An exception was raised when the program ``procnum`` was greater than the list of applicable nodes.

* Fixed `Issue #91 <https://github.com/julien6387/supvisors/issues/91>`_.
  Fix CSS style on the process tables in HTML.

* Fixed `Issue #90 <https://github.com/julien6387/supvisors/issues/90>`_.
  The **Supvisors** *Master* node drives the transition to ``OPERATION``.

* In the Web UI, set the process state color to ``FATAL`` when the process has exited unexpectedly.

* Change the default expected loading to ``0`` in the program rules.

* Python ``Enum`` used for enumerations (not available in Python 2.7).

* Remove ``supvisors_shortcuts`` from source code to get rid of IDE warnings.

* All unit tests updated from ``unittest`` to ``pytest``.

* Include this Change Log to documentation.

* Documentation updated.


0.5 (2021-03-01)
----------------

* New option ``force_synchro_if`` to force the end of the synchronization phase when a subset of nodes are active.

* New starting strategy ``LOCAL`` added to command the starting of an application on the local node only.

* Fixed `Issue #87 <https://github.com/julien6387/supvisors/issues/87>`_.
  Under particular circumstances, **Supvisors** could have multiple *Master* nodes.

* Fixed `Issue #86 <https://github.com/julien6387/supvisors/issues/86>`_.
  The starting and stopping sequences may fail and block when a sub-sequence includes only failed programs.

* Fixed `Issue #85 <https://github.com/julien6387/supvisors/issues/85>`_.
  When using ``#`` in the ``address_list`` program rule of the **Supvisors** rules file, a subset of nodes can optionally be defined.

* Fixed `Issue #84 <https://github.com/julien6387/supvisors/issues/84>`_.
  In the **Supvisors** rules file, program rules can be defined using both model reference and attributes.

* The Web UI uses the default starting strategy of the configuration file.

* The layout of Web UI statistics sections has been rearranged.

* Fixed CSS style missing for ``CHECKING`` node state in tables.

* Star added to the node box of the *Master* instance on the main page.

* Type annotations are added progressively in source code.

* Start switching from ``unittest`` to ``pytest``.

* Logs (especially ``debug`` and ``trace``) updated to remove printed objects.

* Documentation updated.


0.4 (2021-02-14)
----------------

* Auto-refresh button added to all pages.

* Web UI Main page reworked by adding a subdivision of application in node boxes.

* Fixed exception when exiting using ``Ctrl+c`` from shell.

* Fixed exception when rules files is not provided.

* Documentation updated.


0.3 (2020-12-29)
----------------

* Fixed `Issue #81 <https://github.com/julien6387/supvisors/issues/81>`_.
  When **Supvisors** logfile is set to ``AUTO``, **Supvisors** uses the same logger as **Supervisor**.

* Fixed `Issue #79 <https://github.com/julien6387/supvisors/issues/79>`_.
  When ``FATAL`` or ``UNKNOWN`` Process state is forced by **Supvisors**, ``spawnerr`` was missing in the listener payload.

* Useless folder ``rsc_ref`` deleted.

* ``design`` folder moved to a dedicated *GitHub* repository.

* 100% coverage reached in unit tests.

* Documentation updated.


0.2 (2020-12-14)
----------------

* Migration to **Python 3.6**.
  Versions of dependencies are refreshed, more particularly **Supervisor 4.2.1**.

* CSS of Web UI updated / simplified.

* New action added to Host Process page of WebUI: ``tail -f stderr`` button.

* New information actions added to Application page of WebUI:

    * ``description`` field.
    * ``clear logs``, ``tail -f stdout``, ``tail -f stderr`` buttons.

* Fixed `Issue #75 <https://github.com/julien6387/supvisors/issues/75>`_.
  **Supvisors** takes into account the ``username`` and the ``password`` of ``inet_http_server`` in the ``supervisord`` section.

* Fixed `Issue #17 <https://github.com/julien6387/supvisors/issues/17>`_.
  The user selections on the web UI are passed to the URL.

* Fixed `Issue #72 <https://github.com/julien6387/supvisors/issues/72>`_.
  The extra arguments are shared between all **Supvisors** instances.

* ``README.rst`` replaced with ``README.md``.

* Coverage improved in tests.

* Docs target added to Travis-CI.

* Documentation formatting issues fixed.


0.1 (2017-08-11)
----------------

Initial release.
