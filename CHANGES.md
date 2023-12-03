# Change Log

## 0.17.2 (2023-12-04)

* Fix rare I/O exception by joining the `SupervisorsProxy` thread before exiting the `SupvisorsMainLoop`.

* Fix rare exception when host network statistics are prepared for display in the **Supvisors** Web UI in the event
  where network interfaces have different history sizes.

* Fix the Supvisors identifier possibilities when using the distribution rule `SINGLE_INSTANCE`.

* Update the process statistics collector thread so that it exits by itself when `supervisord` is killed.

* Improve the node selection when using the distribution rule `SINGLE_NODE`.

* Use an asynchronous server in the **Supvisors** internal communications.
  The refactoring fixes an issue with the TCP server that sometimes wouldn't bind despite the `SO_REUSEADDR` set.

* Restore the `action` class in the HTML of the **Supvisors** Web UI.

* CI targets added for Python 3.11 and 3.12.


## 0.17 (2023-08-17)

* Fix [Issue #112](https://github.com/julien6387/supvisors/issues/112).
  Write the disabilities file even if no call to `disable` and `enable` XML-RPCs have been done.
  Try to create the folder at startup if it does not exist.

* Fix a case where the `Starter` would block if the process reaches the expected state without reception
  of the corresponding event.

* Fix typo for `zmq` requirement when installing **Supvisors** from `pypi`.

* Fix `flask-restx` dependency in setup according to Python version.

* Fix uncaught exception the request to start a process is rejected due to a lack of resources.
  The exception was dependent from the Python version (absent in 3.6 but raised in 3.9).

* Monkeypatch fix of [Supervisor Issue #1596](https://github.com/Supervisor/supervisor/issues/1596).
  Shutdown of the asyncore socket before it is closed.

* Improve robustness against network failures. All Supervisor events are applied to the local **Supvisors** instance
  before they are published, so that it remains functional despite a network failure.
  The internal TCP sockets are rebound when a network interface becomes up (requires `psutil`).

* Provide a discovery mode where the **Supvisors** instances are added on-the-fly without declaring them in
  the `supvisors_list` option. The function relies on a Multicast Group definition (options `multicast_group`,
  `multicast_interface` and `multicast_ttl` added to that purpose).
  The attribute `discovery_mode` is added to the `get_state` and `get_instance_info` XML-RPCs.

* Add a new option `stereotypes` to support the discovery mode. The `identifiers` of the Application and Program rules
  can now reference a **Supvisors** stereotype in addition to identifiers and aliases.
  By extension, it is made available to the non-discovery mode.

* Add a new option `syncho_options` to enable the user to choose the conditions putting an end to the **Supvisors**
  synchronization phase.
  More particularly when using the new `USER` condition, the **Supvisors** Web UI provides a means to end the
  `INITIALIZATION` state, with optional *Master* selection. The command is also available as an XML-RPC `end_synchro`
  and has been added to `supervisorctl`.

* The new item `@` in the `identifiers` of the Program rules takes the behavior of the item `#` as it was
  before **Supvisors** version 0.13, i.e. the assignment is strictly limited by the length of the `identifiers` list,
  without roll-over.
  NOTE: This is not available for Application rules.

* Use host aliases when looking for the local **Supvisors** instance.

* Use IP address rather than host identification when dealing with `SINGLE_NODE` starting strategy. 

* To prevent the situation that led the `Starter` to block, a new state `CHECKED` is added to `SupvisorsInstanceStates`,
  which is actually a pre-`RUNNING` state.
  Such a **Supvisors** instance is considered active and is updated with received events but cannot be part of any
  starting sequence until all starting jobs in progress are completed.

* Limit the consideration of the process forced state to display in the Application page of the **Supvisors** Web UI,
  so that it does not interfere with the real process state.

* Add `master_identifier` to the output of the XML-RPCs `get_supvisors_state` and `get_instances_info`.
  The `supervisorctl` commands `sstate` and `instance_status` have also been updated.

* Monkeypatch **Supervisor** on-the-fly so that its logger is thread-safe and add log traces in **Supvisors** threads.

* Simplify the **Supvisors** state machine and replace the states `RESTART` and `SHUTDOWN` by a single state `FINAL`.

* Highlight the process line hovered by the cursor in the **Supvisors** Web UI.

* Remove the figures from the **Supvisors** Web UI when `matplotlib` is not installed.

* Add RPC `changeLogLevel` to the JAVA client.

* Do not catch XmlRpc exceptions in the JAVA client.

* Refactoring of the **Supvisors** internal communications.


## 0.16 (2023-03-12)

* Add `websockets` as an option to the **Supvisors** event listener (Python 3.7+ only).

* Re-design the `PyZMQ` event listener using the `zmq.asyncio` support for better commonalities
  with the `wesockets` solution.

* Re-design the statistics collection and compilation.

* The option `stats_enabled` takes additional values to control host and process statistics independently.

* The option `stats_collecting_period` has been added to set the minimum time between process statistics collection.

* The option `stats_periods` accepts float values, not necessarily multiples of 5.

* Fix [Issue #54](https://github.com/julien6387/supvisors/issues/54).
  Add host and process statistics to the **Supvisors** event interface.

* Fix children process CPU times in statistics.

* Fix Solaris mode not taken into account for the process mean CPU value in the **Supvisors** Web UI.

* Fix Flask `start_args` to pass the extra arguments in the URL attributes rather than in the route.

* Only one **Supvisors** instance is running when both `unix_http_server` and `inet_http_server` sections are defined
  in the supervisor configuration file.

* The local **Supvisors** instance is identified as the item having the same fully qualified domain name
  (as returned by `socket.gethostaddr` and `socket.getfqdn`) among the items of the `supvisors_list` option. 

* Use the HTTP server port to help the identification of the local **Supvisors** instance when multiple items
  of the `supvisors_list` option fit and identifier is not set.

* The attribute `process_failure` is added to the `get_instance_info` XML-RPC to inform if there is a process failure
  in the **Supvisors** instance. The attribute is also provided in the event interface and in the `instance_status`
  option of the `supervisorctl` command. 

* Raise an exception when the matching **Supvisors** instance in the `supvisors_list` option is inconsistent
  with the local configuration.

* Add a **Supvisors** logo.


## 0.15 (2022-11-20)

* Publish / Subscribe pattern implemented for **Supvisors** internal communication.
  `PyZmq` is now only used for the optional external publication interface.

* Make **Supvisors** robust to `addProcessGroup` / `removeProcessGroup` / `reloadConfig` Supervisor XML-RPCs.

* Fix process CPU times in statistics so that children processes are all taken into account.

* Fix regression in `supervisorctl application_rules` where the former `distributed` entry was still used
  instead of `distribution`. 

* Fix uncaught exception when an unknown host name or IP address is used in the `supvisors_list` option.

* Fix `ProcessEvent` publication when no resource is available to start a process. 

* Fix `SupvisorsStatus` event in JAVA ZMQ client.

* Manage the `RuntimeError` exception that could be raised by matplotlib when saving a graph.

* Add `all_start` and `all_start_args` to the list of `supervisorctl` commands. These commands respectively invoke
  `supervisor.startProcess` and `supvisors.start_args` on all running **Supvisors** instances.

* Add `tail_limit` and `tailf_limit` options to override the default 1024 bytes used by Supervisor to display
  the Tail pages of the Web UI.

* Inactive Log Clear / Stdout / Stderr buttons in the Web UI if no stdout / stderr is configured. 

* Add resolution to `ProcessStatus` time information and store event time, so that forced state is correctly considered.

* A process is not considered disabled anymore when process rules don't allow any candidate **Supvisors** instance.

* When `psutil` is not installed on a host, the statistics-related options of the Process and Host pages
  of the Web UI are not displayed, just as if the option `stats_enabled` was set to `False`.

* Clarify the exceptions that could be raised in **Supvisors** startup.

* Add a FAQ to the documentation.


## 0.14 (2022-05-01)

* Implement [Supervisor Issue #1054](https://github.com/Supervisor/supervisor/issues/1054).
  Start / Stop / Restart buttons have been added to groups in the Supervisor page of the Web UI so that it is possible
  to start / stop / restart all the processes of the group at once.
  The application state and description have been removed from this table as the information was confusing.

* Fix issue where starting strategies would not work as expected when multiple **Supvisors** instances run on the same
  node but their `host_name` is identified differently in the option `supvisors_list`.

* Replace on-the-fly the Supervisor `gettags` function so that the XML-RPC `system.methodSignature` works with both
  Supervisor and **Supvisors**.

* Use `socket.gethostaddr` to validate the host names provided in the option `supvisors_list`.

* In the Application page of the Web UI, apply a *disabled* status to programs that are disabled on all their possible
  **Supvisors** instances (according to rules and configuration).

* Maintain the auto-refresh set on the **Supvisors** `restart` / `shutdown` actions of the Web UI.

* Change the style of the *matplotlib* graphs.


## 0.13 (2022-02-27)

* Implement [Supervisor Issue #591](https://github.com/Supervisor/supervisor/issues/591).
  It is possible to disable/enable programs using the new `disable` and `enable` XML-RPCs. 
  A new option `disabilities_file` has been added to support the persistence.
  The `disabled` status of the processes is made available through the `supvisors.get_local_process_info` XML-RPC and
  in the process table of the Web UI.

* Fix issue where **Supvisors** may be blocked in the `DEPLOYMENT` phase due to late process events.

* Add a new `start_any_process` XML-RPC that starts one process whose namespec matches the regular expression.

* Add a `wait` parameter to the `update_numprocs` XML-RPC.

* Add the principle of **Supvisors** modes to the output of the XML-RPCs `get_supvisors_state` and `get_instance_info`.
  The modes are linked to the existence of jobs in progress in `Starter` and `Stopper`.

* The **Supvisors** modes are displayed to the Main page of the Web UI and the **Supvisors** instance modes are
  displayed to the Process and Host pages of the Web UI. In the navigation menu, the local **Supvisors** instance
  points out the **Supvisors** instances where the modes are activated, and the applications involved in its own
  `Starter` or `Stopper`.

* When using the item `#` in the `identifiers` of the Application or Program rules and with a number of candidate
  applications or processes greater than the candidate `identifiers`, the assignment is performed by rolling over
  the `identifiers` list. 

* Add pid and uptime information to the `supervisord` entry of the process table in the Web UI.

* The application rules of a **Supvisors** rules file can be inserted in any order.

* Protect the Supervisor thread against any exception that could be raised by **Supvisors** when processing a Supervisor
  event.

* Provide a Flask server that can be added as a Supervisor program to interact with **Supvisors** using a REST API.

* Update the CSS style of the inactive buttons in the Web UI.

* Fix CSS resources table cell height with recent versions of Firefox.

* Update the Web UI to allow multiple processes per line in the **Supvisors** instance boxes.

* Remove support to deprecated option `distributed` and to the possibility to have the `program` element directly
  under the `application element` in a **Supvisors** rules file.


## 0.12 (2022-01-26)

* Fix crash following a `supervisorctl update` as the group added doesn't include `extra_args` and `command_ref`
  attributes in the Supervisor internal structure.

* Fix crash when the state of the **Supvisors** master is received before any **Supvisors** instance has been confirmed.

* Fix crash when receiving process state events from a **Supvisors** instance that has been checked while it was in a
  `RESTARTING` state.

* Fix regression in **Supvisors** restarting / shutting down as the *Master* would actually restart / shut down
  before notifying the other **Supvisors** instances of its state. The new **Supvisors** state `RESTART` has been
  introduced. 

* Add `supervisord` entry to the process table of the **Supvisors** instance in the Web UI.
  This entry provides process statistics and the possibility to view the Supervisor logs.

* Fix issue in Web UI with the Solaris mode not applied to the process CPU plot.

* Fix CSS for Supvisors instance boxes (table headers un-stickied) in the Main page of the Web UI.

* Fix process children CPU times counted twice in statistics.

* Add regex support to the `pattern` attribute of the `application` and `program` elements of the **Supvisors** rules
  file.

* The `distribution` option has been added to replace the `distributed` option in the **Supvisors** rules file.
  The `distributed` option is deprecated and will be removed in the next version.

* Update the starting strategies so that the node load is considered in the event where multiple **Supvisors** instances
  are running on the same node. The `LESS_LOADED_NODE` and `MOST_LOADED_NODE` starting strategies have been added.

* Update the `RunningFailureHandler` so that `Starter` and `Stopper` actions are all stored before they are actually 
  triggered.

* Add the `RESTART` and `SHUTDOWN` strategies to the `running_failure_strategy` option.

* Update `Starter` and `Stopper` so that event timeouts are based on ticks rather than time.

* Update `InfanticideStrategy` and `SenicideStrategy` so that the conciliation uses the `Stopper`.
  This avoids duplicated conciliation requests when entering the `CONCILIATION` state.

* When receiving a forced state due to a `Starter` or `Stopper` timeout, check if the expected process state has been
  reached before actually forcing the state. Events may have crossed.

* The `programs` section has been added in the `application` section of the **Supvisors** rules file.
  All `program` definitions should be placed in this section rather than directly in the `application` section.
  The intention is for the next **Supvisors** version to be able to declare application options in any order.
  Note that having `program` sections directly in the `application` section is still supported but deprecated
  and will be removed in the next version.

* Add the `starting_failure_strategy` option in the `program` section of the **Supvisors** rules file.
  It supersedes the values eventually set in the `application` section.

* Add the `inactivity_ticks` option to the **Supvisors** section of the Supervisor configuration file to enable more
  flexibility in a congested system.

* Add `node_name` and `port` information to the result of the `get_instance_info` XML-RPC and to the instance status
  of the **Supvisors** event listener.

* In the Process page of the Web UI, add buttons to shrink / expand all applications.

* Use a different gradient in the Web UI for running processes that have ever crashed.

* Fix CSS process table cell height with recent versions of Firefox.

* Use hexadecimal strings for the `shex` attribute in the Web UI URL. 

* Add `action` class to the start/stop/restart/shutdown buttons in the headers of the **Supvisors** web pages.

* Move PyZmq sockets creation to the main thread so that a bind error is made explicit in log traces.

* Remove support to deprecated options, attributes and XML-RPCs (`address_list`, `force_synchro_if`, `rules_file`,
  `address_name`, `addresses`, `get_master_address`, `get_address_info` and `get_all_addresses_info`).


## 0.11 (2022-01-02)

* Fix [Issue #99](https://github.com/julien6387/supvisors/issues/99).
  Update the **Supvisors** design so that it can be used to supervise multiple Supervisor instances on multiple nodes.
  This update had a major impact on the source code. More particularly:
  - The XML-RPCs `get_master_identifier`, `get_instance_info` and `get_all_instances_info` have been added to replace
    `get_master_address`, `get_address_info` and `get_all_addresses_info`.
  - The `supervisorctl` command `instance_status` has been added to replace `address_status`.
  - The XML-RPCs that would return attributes `address_name` and `addresses` are now returning `identifier` and
    `identifiers` respectively. This impacts the following XML-RPCs (and related `supervisorctl` commands):
    - `get_application_info`
    - `get_all_application_info`
    - `get_application_rules`
    - `get_address_info`
    - `get_all_addresses_info`
    - `get_all_process_info`
    - `get_process_info`
    - `get_process_rules`
    - `get_conflicts`.
  - The `supvisors_list` option has been added to replace `address_list` in the **Supvisors** section of the Supervisor
    configuration file. This option accepts a more complex definition: `<identifier>host_name:http_port:internal_port`.
    Note that the simple `host_name` is still supported in the event where **Supvisors** doesn't have to deal
    with multiple Supervisor instances on the same node.
  - The `core_identifiers` option has been added to replace `force_synchro_if` in the **Supvisors** section of the
    Supervisor configuration file. It targets the names deduced from the `supvisors_list` option.
  - The `identifiers` option has been added to replace the `addresses` option in the **Supvisors** rules file.
    This option targets the names deduced from the `supvisors_list` option.
  - The `address`-like attributes, XML-RPCs and options are deprecated and will be removed in the next version.

* Fix [Issue #98](https://github.com/julien6387/supvisors/issues/98).
  Move the heartbeat emission to the Supvisors thread to avoid being impacted by a Supervisor momentary freeze.
  On the heartbeat reception part, consider that the node is `SILENT` based on a number of ticks instead of time.

* Fix issue with `supvisors.stop_process` XML-RPC that wouldn't stop all processes when any of the targeted processes
  is already stopped.

* Fix exception when authorization is received from a node that is not in `CHECKING` state. 

* Fix regression (missing disconnect) on node isolation when fencing is activated.

* Fix issue in statistics compiler when network interfaces are dynamically created / removed.

* Refactoring of `Starter` and `Stopper`.

* The module `rpcrequests` has been removed because useless.
  The function `getRPCInterface` of th module `supervisor.childutils` does the job.

* The `startsecs` and `stopwaitsecs` program options have been added to the results of `get_all_local_process_info` and
  `get_local_process_info`.

* The option `rules_file` is updated to `rules_files` and supports multiple files for **Supvisors** rules.
  The option `rules_file` is thus deprecated and will be removed in the next version.

* Add a new `restart_sequence` XML-RPC to trigger a full application start sequence.

* Update the `restart_application` and `restart_process` XML-RPC so that processes can restart themselves using them.

* Add `expected_exit` to the output of `supervisorctl sstatus` when the process is `EXITED`.

* Add the new option `stats_enabled` to enable/disable the statistics function.

* Update `start_process`, `stop_process`, `restart_process`, `process_rules` in `supervisorctl` so that calls are made
  on each individually process rather than process group when `all` is used as parameter.

* Add exit codes to erroneous **Supvisors** calls in `supervisorctl`.

* When aborting jobs when re-entering the `INITIALIZATION` state, clear the structure holding the jobs in progress.
  It has been found to stick **Supvisors** in the `DEPLOYMENT` state in the event where the *Master* node is temporarily
 `SILENT`.

* Restrict the use of the XML-RPCs `start_application`, `stop_application`, `restart_application` to *Managed*
  applications only.

* Review the logic of the refresh button in the Web UI.

* Add node time to the node boxes in the Main page of the Web UI.

* Sort alphabetically the entries of the application menu of the Web UI.

* Update the mouse pointer look on nodes in the Main and Host pages of the Web UI.

* Remove the useless timecode in the header of the Process and Host pages of the Web UI as it is now provided
  at the bottom right of all pages.

* Add class "action" to Web UI buttons that trigger an XML-RPC.

* Switch from Travis-CI to GitHub Actions for continuous integration.


## 0.10 (2021-09-05)

* Implement [Supervisor Issue #177](https://github.com/Supervisor/supervisor/issues/177).
  It is possible to update dynamically the program numprocs using the new `update_numprocs` XML-RPC. 

* Add targets **Python 3.7** and **Python 3.8** to Travis-CI.


## 0.9 (2021-08-31)

* Enable the hash '#' for the `addresses` of a non-distributed application.

* Add `supvisorsctl` to pally the lack of support of `supervisorctl` when used with `--serverurl URL` option.
  See related [Supervisor Issue #1455](https://github.com/Supervisor/supervisor/issues/1455).

* Provide `breed.py` as a binary of **Supvisors**: `supvisors_breed`.
  The script only considers group duplication as it is fully valid to include multiple times a program definition
  in several groups.

* Move the contents of the `[supvisors]` section into the `[rpcinterface:supvisors]` section and benefit from the
  configuration structure provided by Supervisor. The `[supvisors]` section itself is thus obsolete.

* Remove deprecated support of `pattern` elements.

* Fix issue when using the Web UI Application page from a previous launch.

* Invert the stop sequence logic, starting from the greatest ``stop_sequence`` number to the lowest one.

* When ``stop_sequence`` is not set in the rules files, it is defaulted to the ``start_sequence`` value.
  With the new stop sequence logic, the stop sequence is by default exactly the opposite of the start sequence.

* Fix Nodes' column width for `supervisorctl application_rules`.

* `CHANGES.rst` replaced with `CHANGES.md`.

* 'Scenario 3' has been added to the **Supvisors** use cases.

* A 'Gathering' configuration has been added to the **Supvisors** use cases. It combines all uses cases.


## 0.8 (2021-08-22)

* Fix exception in `INITIALIZATION` state when the *Master* declared by other nodes is not RUNNING yet and
  the *core nodes* are RUNNING.

* Fix exception when program rules and extra arguments are tested against a program unknown to the local Supervisor.

* Fix issue about program patterns that were applicable to all elements. The scope of program patterns is now limited
  to their owner application.

* Fix issue with infinite tries of application restart when the process cannot be started due to a lack of resources
  and `RESTART_APPLICATION` is set on the program in the **Supvisors** rules file.

* Fix issue about application state not updated after a node has become silent.

* Fix issue when choosing a node in `Starter`. Apply the requests that have not been satisfied yet for
  non-distributed applications.

* Review logic for application major / minor failures.

* Simplify the insertion of applications to start or stop in Commander jobs.

* Add support for application patterns in the **Supvisors** rules file.

* In the **Supvisors** rules file, `pattern` elements are **deprecated** and are replaced by `program` elements
  with a `pattern` attribute instead of a `name` attribute.
  Support for `pattern` elements will be removed in the next version of **Supvisors**.

* Node aliases have been added to the **Supvisors** rules file.

* Add the current node to all pages of Web UI to be aware of the node that displays the page.

* The Web UI is updated to handle a large list of applications, nodes, processor cores and network interfaces.

* In the Process page of the Web UI, expand / shrink actions are not applicable to programs that are not owned
  by a Supervisor group.

* In the application navigation menu of the Web UI, add a red light near the Applications title if any application
  has raised a failure.

* In the Application page of the Web UI, default starting strategy is the starting strategy defined
  in the **Supvisors** rules file for the application considered.

* In the Application ang Process page, the detailed process statistics can be deselected.

* Titles added to the output of :program:`supervisorctl` `address_status` and `application_info`.

* The XML schema has been moved to a separate file `rules.xsd`.

* Remove dependency to *netifaces* as *psutil* provides the function.

* 'Scenario 2' has been added to the **Supvisors** use cases.

* A script `breed.py` has been added to the installation package.
  It can be used to duplicate the applications based on a template configuration and more particularly used to prepare
  the Scenario 2 of the **Supvisors** use cases.


## 0.7 (2021-08-15)

* Fix [Issue #92](https://github.com/julien6387/supvisors/issues/92).
  The *Master* drives the state of all **Supvisors** instances and a simplified state machine has been assigned
  to non-master **Supvisors** instances. The loss of the *Master* instance is managed in all relevant states.

* Fix issue about applications that would be started automatically whereas their `start_sequence` is 0.
  The regression has been introduced during the implementation of applications repair in **Supvisors 0.6**.

* Enable stop sequence on *Unmanaged* applications.

* In the application navigation menu of the Web UI, add a red light to applications having raised a failure.

* New application rules `distributed` and `addresses` added to the **Supvisors** rules file.
  Non-distributed applications have all their processes started on the same node chosen in accordance with the
  `addresses` and the `starting_strategy`.

* Add the `starting_strategy` option to the `application` section of the **Supvisors** rules file.

* Fix issue when choosing a node in `Starter`. The starting strategies considers the current load of the nodes
  and includes the requests that have not been satisfied yet.

* Fix issue with infinite process restart when the process crashes and `RESTART_PROCESS` is set on the program
  in the **Supvisors** rules file. When the process crashes, only the *Supervisor* `autorestart` applies.
  The **Supvisors** `RESTART_PROCESS` applies only when the node becomes inactive.

* Fix exception when forcing the state on a process that is unknown to the local Supervisor.

* Promote the `RESTART_PROCESS` into `RESTART_APPLICATION` if the application is stopped.

* For the *Master* election, give a priority to nodes declared in the `forced_synchro_if` option if used.

* When using the `forced_synchro_if` option and when `auto_fence` is activated, do not isolate nodes as long as
  `synchro_timeout` has not passed.

* In the `INITALIZATION` state, skip the synchronization phase upon notification of a known *Master* and adopt it.

* Add reciprocity to isolation even if `auto_fence` is not activated.

* In the process description of the Web UI Application page, add information about the node name.
  In particular, it is useful to know where the process was running when it is stopped.

* Start adding use cases to documentation, inspired by real examples.
  'Scenario 1' has been added.


## 0.6 (2021-08-01)

* Applications that are not declared in the **Supvisors** rules file are not *managed*.
  *Unmanaged* applications have no start/stop sequence, no state and status (always STOPPED) and **Supvisors**
  does not raise a conflict if multiple instances are running over multiple nodes.

* Improve **Supvisors** stability when dealing with remote programs undefined locally.

* Add expand / shrink actions to applications to the `ProcInstanceView` of the Web UI.

* Upon authorization of a new node in **Supvisors**, back to `DEPLOYMENT` state to repair applications.

* Add RPC `change_log_level` to dynamically change the **Supvisors** logger level.

* Application state is evaluated only against the starting sequence of its processes.

* Fix blocking issue when *Master* is stopped while in `DEPLOYMENT` state.

* Fix issue with applications that would not fully stop when using the `STOP_APPLICATION` starting failure strategy.

* Fix issue related to [Issue #85](https://github.com/julien6387/supvisors/issues/85).
  An exception was raised when the program `procnum` was greater than the list of applicable nodes.

* Fix [Issue #91](https://github.com/julien6387/supvisors/issues/91).
  Fix CSS style on the process tables in HTML.

* Fix [Issue #90](https://github.com/julien6387/supvisors/issues/90).
  The **Supvisors** *Master* node drives the transition to `OPERATION`.

* In the Web UI, set the process state color to `FATAL` when the process has exited unexpectedly.

* Change the default expected loading to `0` in the `program` section of the **Supvisors** rules file.

* Python `Enum` used for enumerations (not available in Python 2.7).

* Remove `supvisors_shortcuts` from source code to get rid of IDE warnings.

* All unit tests updated from `unittest` to `pytest`.

* Include this Change Log to documentation.


## 0.5 (2021-03-01)

* New option `force_synchro_if` to force the end of the synchronization phase when a subset of nodes is active.

* New starting strategy `LOCAL` added to command the starting of an application on the local node only.

* Fix [Issue #87](https://github.com/julien6387/supvisors/issues/87).
  Under particular circumstances, **Supvisors** could have multiple *Master* nodes.

* Fix [Issue #86](https://github.com/julien6387/supvisors/issues/86).
  The starting and stopping sequences may fail and block when a sub-sequence includes only failed programs.

* Fix [Issue #85](https://github.com/julien6387/supvisors/issues/85).
  When using `#` in the `address_list` program rule of the **Supvisors** rules file, a subset of nodes can optionally
  be defined.

* Fix [Issue #84](https://github.com/julien6387/supvisors/issues/84).
  In the **Supvisors** rules file, program rules can be defined using both model reference and attributes.

* The Web UI uses the default starting strategy of the configuration file.

* The layout of Web UI statistics sections has been rearranged.

* Fix CSS style missing for `CHECKING` node state in tables.

* Star added to the node box of the *Master* instance on the main page.

* Type annotations are added progressively in source code.

* Start switching from `unittest` to `pytest`.

* Logs (especially `debug` and `trace`) updated to remove printed objects.


## 0.4 (2021-02-14)

* Auto-refresh button added to all pages.

* Web UI Main page reworked by adding a subdivision of application in node boxes.

* Fix exception when exiting using `Ctrl+c` from shell.

* Fix exception when rules files is not provided.


## 0.3 (2020-12-29)

* Fix [Issue #81](https://github.com/julien6387/supvisors/issues/81).
  When **Supvisors** logfile is set to `AUTO`, **Supvisors** uses the same logger as **Supervisor**.

* Fix [Issue #79](https://github.com/julien6387/supvisors/issues/79).
  When `FATAL` or `UNKNOWN` Process state is forced by **Supvisors**, `spawnerr` was missing in the listener payload.

* Useless folder `rsc_ref` deleted.

* `design` folder moved to a dedicated *GitHub* repository.

* 100% coverage reached in unit tests.


## 0.2 (2020-12-14)

* Migration to **Python 3.6**.
  Versions of dependencies are refreshed, more particularly **Supervisor 4.2.1**.

* CSS of Web UI updated / simplified.

* New action added to Host Process page of WebUI: `tail -f stderr` button.

* New information actions added to Application page of WebUI:

    * `description` field.
    * `clear logs`, `tail -f stdout`, `tail -f stderr` buttons.

* Fix [Issue #75](https://github.com/julien6387/supvisors/issues/75).
  **Supvisors** takes into account the `username` and the `password` of `inet_http_server` in the `supervisord` section.

* Fix [Issue #17](https://github.com/julien6387/supvisors/issues/17).
  The user selections on the web UI are passed to the URL.

* Fix [Issue #72](https://github.com/julien6387/supvisors/issues/72).
  The extra arguments are shared between all **Supvisors** instances.

* `README.rst` replaced with `README.md`.

* Coverage improved in tests.

* Docs target added to Travis-CI.


## 0.1 (2017-08-11)

Initial release.
