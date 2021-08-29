# Change Log

## 0.9 (2021-xx-xx)

* Enable the hash '#' for the `addresses` of a non-distributed application.

* Add `supvisorsctl` to pally the lack of support of `supervisorctl` when used with `--serverurl URL` option.
  See related [Supervisor Issue #1455](https://github.com/Supervisor/supervisor/issues/1455).

* Provide `breed.py` as a binary of **Supvisors**: `supvisors_breed`.

* Move the contents of the `[supvisors]` section into the `[rpcinterface:supvisors]` section and benefit from the
  configuration structure provided by Supervisor. The `[supvisors]` section itself is thus obsolete.

* Remove deprecated support of `pattern` elements.

* Fixed issue when using the Web UI Application page from a previous launch.

* Fixed Nodes column width for `supervisorctl application_rules`.

* `CHANGES.rst` replaced with `CHANGES.md`.

* Scenario 3 has been added to the **Supvisors** use cases.

* Update documentation.


## 0.8 (2021-08-22)

* Fixed exception in `INITIALIZATION` state when the *Master* declared by other nodes is not RUNNING yet and
  the *core nodes* are RUNNING.

* Fixed exception when program rules and extra arguments are tested against a program unknown to the local Supervisor.

* Fixed issue about program patterns that were applicable to all elements. The scope of program patterns is now limited
  to their owner application.

* Fixed issue with infinite tries of application restart when the process cannot be started due to a lack of resources
  and `RESTART_APPLICATION` is set on the program in the **Supvisors** rules file.

* Fixed issue about application state not updated after a node has become silent.

* Fixed issue when choosing a node in `Starter`. Apply the requests that have not been satisfied yet for
  non-distributed applications.

* Logic for application major / minor failures reviewed.

* Simplify the insertion of applications to start or stop in Commander jobs.

* In the rules file, support for application patterns has been added.

* In the rules file, `pattern` elements are **deprecated** and are replaced by `program` elements with a `pattern`
  attribute instead of a `name` attribute.
  Support for `pattern` elements will be removed in the next version of **Supvisors**.

* Node aliases have been added to the rules file.

* Add the current node to all pages of Web UI to be aware of the node that displays the page.

* The Web UI is updated to handle a large list of applications, nodes, processor cores and network interfaces.

* In the Process page of the Web UI, expand / shrink actions are not applicable to programs that are not owned
  by a Supervisor group.

* In the application navigation menu of the Web UI, add a red light near the Applications title if any application
  has raised a failure.

* In the Application page of the Web UI, default starting strategy is the starting strategy defined in the rules file
  for the application considered.

* In the Application ang Process page, the detailed process statistics can be deselected.

* Titles added to the output of :program:`supervisorctl` `address_status` and `application_info`.

* The XML schema has been moved to a separate file `rules.xsd`.

* Remove dependency to *netifaces* as *psutil* provides the function.

* Scenario 2 has been added to the **Supvisors** use cases.

* A script `breed.py` has been added to the install package.
  It can be used to duplicate the applications based on a template configuration and more particularly used to prepare
  the Scenario 2 of the **Supvisors** use cases.

* Update documentation.


## 0.7 (2021-08-15)

* Fixed [Issue #92](https://github.com/julien6387/supvisors/issues/92).
  The *Master* drives the state of all **Supvisors** instances and a simplified state machine has been assigned
  to non-master **Supvisors** instances. The loss of the *Master* instance is managed in all relevant states.

* Fixed issue about applications that would be started automatically whereas their `start_sequence` is 0.
  The regression has been introduced during the implementation of applications repair in **Supvisors 0.6**.

* Enable stop sequence on *Unmanaged* applications.

* In the application navigation menu of the Web UI, add a red light to applications having raised a failure.

* New application rules `distributed` and `addresses` added to the **Supvisors** rules file.
  Non-distributed applications have all their processes started on the same node chosen in accordance with the
  `addresses` and the `starting_strategy`.

* Starting strategy added to the application rules.

* Fixed issue when choosing a node in `Starter`. The starting strategies considers the current load of the nodes
  and includes the requests that have not been satisfied yet.

* Fixed issue with infinite process restart when the process crashes and `RESTART_PROCESS` is set on the program
  in the **Supvisors** rules file. When the process crashes, only the *Supervisor* `autorestart` applies.
  The **Supvisors** `RESTART_PROCESS` applies only when the node becomes inactive.

* Fixed exception when forcing the state on a process that is unknown to the local Supervisor.

* Promote the `RESTART_PROCESS` into `RESTART_APPLICATION` if the application is stopped.

* For the *Master* election, give a priority to nodes declared in the `forced_synchro_if` option if used.

* When using the `forced_synchro_if` option and when `auto_fence` is activated, do not isolate nodes as long as
  `synchro_timeout` has not passed.

* In the `INITALIZATION` state, skip the synchronization phase upon notification of a known *Master* and adopt it.

* Add reciprocity to isolation even if `auto_fence` is not activated.

* In the process description of the Web UI Application page, add information about the node name.
  In particular, it is useful to know where the process was running when it is stopped.

* Start adding use cases to documentation, inspired by real examples.
  Scenario 1 has been added.

* Documentation updated.


## 0.6 (2021-08-01)

* Applications that are not declared in the rules file are not *managed*.
  *Unmanaged* applications have no start/stop sequence, no state and status (always STOPPED) and **Supvisors**
  does not raise a conflict if multiple instances are running over multiple nodes.

* Improve **Supvisors** stability when dealing with remote programs undefined locally.

* Add expand / shrink actions to applications to the `ProcAddressView` of the Web UI.

* Upon authorization of a new node in **Supvisors**, back to `DEPLOYMENT` state to repair applications.

* Add RPC `change_log_level` to dynamically change the **Supvisors** logger level.

* Application state is evaluated only against the starting sequence of its processes.

* Fixed blocking issue when *Master* is stopped while in `DEPLOYMENT` state.

* Fixed issue with applications that would not fully stop when using the `STOP_APPLICATION` starting failure strategy.

* Fixed issue related to [Issue #85](https://github.com/julien6387/supvisors/issues/85).
  An exception was raised when the program `procnum` was greater than the list of applicable nodes.

* Fixed [Issue #91](https://github.com/julien6387/supvisors/issues/91).
  Fix CSS style on the process tables in HTML.

* Fixed [Issue #90](https://github.com/julien6387/supvisors/issues/90).
  The **Supvisors** *Master* node drives the transition to `OPERATION`.

* In the Web UI, set the process state color to `FATAL` when the process has exited unexpectedly.

* Change the default expected loading to `0` in the program rules.

* Python `Enum` used for enumerations (not available in Python 2.7).

* Remove `supvisors_shortcuts` from source code to get rid of IDE warnings.

* All unit tests updated from `unittest` to `pytest`.

* Include this Change Log to documentation.

* Documentation updated.


## 0.5 (2021-03-01)

* New option `force_synchro_if` to force the end of the synchronization phase when a subset of nodes are active.

* New starting strategy `LOCAL` added to command the starting of an application on the local node only.

* Fixed [Issue #87](https://github.com/julien6387/supvisors/issues/87).
  Under particular circumstances, **Supvisors** could have multiple *Master* nodes.

* Fixed [Issue #86](https://github.com/julien6387/supvisors/issues/86).
  The starting and stopping sequences may fail and block when a sub-sequence includes only failed programs.

* Fixed [Issue #85](https://github.com/julien6387/supvisors/issues/85).
  When using `#` in the `address_list` program rule of the **Supvisors** rules file, a subset of nodes can optionally be defined.

* Fixed [Issue #84](https://github.com/julien6387/supvisors/issues/84).
  In the **Supvisors** rules file, program rules can be defined using both model reference and attributes.

* The Web UI uses the default starting strategy of the configuration file.

* The layout of Web UI statistics sections has been rearranged.

* Fixed CSS style missing for `CHECKING` node state in tables.

* Star added to the node box of the *Master* instance on the main page.

* Type annotations are added progressively in source code.

* Start switching from `unittest` to `pytest`.

* Logs (especially `debug` and `trace`) updated to remove printed objects.

* Documentation updated.


## 0.4 (2021-02-14)

* Auto-refresh button added to all pages.

* Web UI Main page reworked by adding a subdivision of application in node boxes.

* Fixed exception when exiting using `Ctrl+c` from shell.

* Fixed exception when rules files is not provided.

* Documentation updated.


## 0.3 (2020-12-29)

* Fixed [Issue #81](https://github.com/julien6387/supvisors/issues/81).
  When **Supvisors** logfile is set to `AUTO`, **Supvisors** uses the same logger as **Supervisor**.

* Fixed [Issue #79](https://github.com/julien6387/supvisors/issues/79).
  When `FATAL` or `UNKNOWN` Process state is forced by **Supvisors**, `spawnerr` was missing in the listener payload.

* Useless folder `rsc_ref` deleted.

* `design` folder moved to a dedicated *GitHub* repository.

* 100% coverage reached in unit tests.

* Documentation updated.


## 0.2 (2020-12-14)

* Migration to **Python 3.6**.
  Versions of dependencies are refreshed, more particularly **Supervisor 4.2.1**.

* CSS of Web UI updated / simplified.

* New action added to Host Process page of WebUI: `tail -f stderr` button.

* New information actions added to Application page of WebUI:

    * `description` field.
    * `clear logs`, `tail -f stdout`, `tail -f stderr` buttons.

* Fixed [Issue #75](https://github.com/julien6387/supvisors/issues/75).
  **Supvisors** takes into account the `username` and the `password` of `inet_http_server` in the `supervisord` section.

* Fixed [Issue #17](https://github.com/julien6387/supvisors/issues/17).
  The user selections on the web UI are passed to the URL.

* Fixed [Issue #72](https://github.com/julien6387/supvisors/issues/72).
  The extra arguments are shared between all **Supvisors** instances.

* `README.rst` replaced with `README.md`.

* Coverage improved in tests.

* Docs target added to Travis-CI.

* Documentation formatting issues fixed.


## 0.1 (2017-08-11)

Initial release.
