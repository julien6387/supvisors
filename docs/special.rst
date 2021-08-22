Special Features
================

.. _synchronizing:

Synchronizing |Supvisors| instances
-------------------------------------

The ``INITIALIZATION`` state of |Supvisors| is used as a synchronization phase so that all |Supvisors| instances
are mutually aware of each other.

The following options defined in the :ref:`supvisors_section` of the |Supervisor| configuration file are particularly
used for synchronizing multiple instances of |Supervisor|:

    * ``address_list``,
    * ``force_synchro_if``,
    * ``internal_port``,
    * ``synchro_timeout``,
    * ``auto_fence``.

Once started, all |Supvisors| instances publish the events received, especially the ``TICK`` events that are
triggered every 5 seconds, on their ``PUBLISH`` *ZeroMQ* socket bound on the ``internal_port``.

On the other side, all |Supvisors| instances start a thread that subscribes to the internal events
through an internal ``SUBSCRIBE`` *ZeroMQ* socket connected to the ``internal_port`` of **all** nodes
of the ``address_list``.

At the beginning, all nodes are in an ``UNKNOWN`` state.
When the first ``TICK`` event is received from a remote |Supvisors| instance, a sort of hand-shake is performed
between the 2 nodes. The local |Supvisors| instance:

    * sets the remote node state to ``CHECKING``,
    * performs a couple of XML-RPC to the remote |Supvisors| instance:

        + ``supvisors.get_master_address()`` and ``supvisors.get_supvisors_state()`` in order to know if the remote
          instance is already in an established state.
        + ``supvisors.get_address_info(local_address)`` in order to know how the local node is perceived
          by the remote instance.

At this stage, 2 possibilities:

    * the local |Supvisors| instance is seen as ``ISOLATED`` by the remote instance:

        + the remote node is then reciprocally set to ``ISOLATED``,
        + the *URL* of the remote |Supvisors| instance is disconnected from the ``SUBSCRIBE`` PyZMQ_ socket,

    * the local |Supvisors| instance is NOT seen as ``ISOLATED`` by the remote instance:

        + a ``supervisor.getAllProcessInfo()`` XML-RPC is requested to the remote instance,
        + the processes information is loaded into the internal data structure,
        + the remote node is finally set to ``RUNNING``.

When all |Supvisors| instances are identified as ``RUNNING`` or ``ISOLATED``, the synchronization is completed.
|Supvisors| then is able to work with the set (or subset) of nodes declared in ``address_list``.

However, it may happen that some |Supvisors| instances do not publish (very late starting, no starting at all,
system down, network down, etc). Each |Supvisors| instance waits for ``synchro_timeout`` seconds to give a chance
to all other instances to publish. When this delay is exceeded, all the |Supvisors| instances that are **not**
identified as ``RUNNING`` or ``ISOLATED`` are set to:

    * ``SILENT`` if `Auto-Fencing`_ is **not** activated,
    * ``ISOLATED`` if `Auto-Fencing`_ is activated.

Another possibility is when it is predictable that some nodes may be started later. For example, the pool of nodes
may include servers that will always be started from the very beginning and workstations that may be started only
on demand. In this case, it would be a pity to always wait for ``synchro_timeout`` seconds. That's why the
``force_synchro_if`` attribute has been introduced so that the synchronization phase is considered completed
when a subset of the nodes declared in ``address_list`` are ``RUNNING``.

Whatever the number of available nodes, |Supvisors| elects a *Master* among the active nodes and enters
the ``DEPLOYMENT`` state to start automatically the applications.
By default, the *Master* node is the node having the smallest name among all the active nodes, unless the attribute
``force_synchro_if`` is used. In the latter case, candidates are taken from this list in priority.

.. note:: *About late nodes*

    Back to this case, here is what happens when a node is started while the others are already in ``OPERATION``.
    During the hand-shake, the local |Supvisors| instance gets the *Master* identified by the remote |Supvisors|.
    That confirms that the local node is a late starter and thus the local |Supvisors| instance adopts this *Master*
    too and skips the synchronization phase.


.. _auto_fencing:

Auto-Fencing
------------

Auto-fencing is applied when the ``auto_fence`` option of the :ref:`supvisors_section` is set.
It takes place when one of the |Supvisors| instance is seen as inactive (crash, system power down, network failure)
from the other |Supvisors| instances.

In this case, the running |Supvisors| instances disconnect the corresponding URL from their subscription socket.
The Address is marked as ``ISOLATED`` and, in accordance with the rules defined and the value of the ``autorestart``
option of the program, |Supvisors| may try to restart somewhere else the processes that were eventually running
on that node.

If the incriminated node restarts, and the |Supvisors| instance is restarted on that system too, the isolation
doesn't prevent the new |Supvisors| instance to receive events from the other instances that have isolated it.
Indeed, it is not possible to filter the subscribers from the ``PUBLISH`` side of a ZeroMQ socket.

That's why a kind of port-knocking is performed in :ref:`synchronizing`.
Each newly arrived |Supvisors| instance asks to the others if it has been previously isolated before taking
into account the incoming events.

In the case of a network failure, the same mechanism is of course applied on the other side.
Here comes the premises of a *split-brain syndrome*, as it leads to have 2 separate and identical sets of applications.

If the network failure is fixed, both sets of |Supvisors| are still running but do not communicate between them.

.. attention::

    |Supvisors| does NOT isolate the nodes at the Operating System level, so that when the incriminated nodes
    become active again, it is still possible to perform network requests between all nodes, despite the
    |Supvisors| instances do not communicate anymore.

    Similarly, it is outside the scope of |Supvisors| to isolate the nodes at application level.
    It is the user's responsibility to isolate his applications.


.. _extra_arguments:

Extra Arguments
----------------

When using |Supervisor|, colleagues have often asked if it would be possible to add extra arguments to the command
line of a program without declaring them in the ini file. Indeed, the applicative context is evolving at runtime
and it may be quite useful to give some information to the new process (options, path, URL of a server,
URL of a display, ...), especially when dealing with distributed applications.

With |Supervisor|, it is possible to inform the process with a ``supervisor.sendProcessStdin`` XML-RPC.
The first drawback is that it requires to update the source code of an existing program that is already capable of
reading instructions from its command line. That is not always possible.
On the other hand, colleagues found the solution so clumsy that they finally preferred to use a dedicated com
to configure the process.

So, |Supvisors| introduces new XML-RPCs that are capable of taking into account extra arguments that are passed
to the command line before the process is started:

   * ``supvisors.start_args``: start a process on the local system,
   * ``supvisors.start_process``: start a process using a starting strategy.

.. hint::

    These additional commands are an answer to the following |Supervisor| request:

        * `#1023 - Pass arguments to program when starting a job? <https://github.com/Supervisor/supervisor/issues/1023>`_

.. note::

    The extra arguments of the program are shared by all |Supervisor| instances.
    Once used, they are published through a |Supvisors| internal event and are stored directly into the |Supervisor|
    internal configuration of the programs.

    In other words, considering 2 nodes A and B, a process that is started on node A with extra arguments and
    configured to restart on node crash (refer to `Running Failure strategy`_), if the node A crashes (or simply
    becomes unreachable), the process will be restarted on node B with the same extra arguments.

.. attention::

    A limitation however: the extra arguments are reset each time a new node connects to the other ones,
    either because it has started later or because it has been disconnected for a while due to a network issue.


.. _starting_strategy:

Starting strategy
-----------------

|Supvisors| provides a means to start a process without telling explicitly where it has to be started,
and in accordance with the rules defined for this program, i.e. the ``address_list``.


Choosing a node
~~~~~~~~~~~~~~~

The following rules are applicable whatever the chosen strategy:

    * the process must not be already in a *running* state in a broad sense, i.e. ``RUNNING``, ``STARTING``
      or ``BACKOFF`` ;
    * the program definition must be known to the node ;
    * the node must be ``RUNNING`` ;
    * the *loading* of the node must not exceed 100% when adding the ``loading`` of the process to be started.

The *loading* of the chosen node is defined as the sum of the ``loading`` of each process running on this address.

When applying the ``CONFIG`` strategy, |Supvisors| chooses the first node available in the ``address_list``.

When applying the ``LESS_LOADED`` strategy, |Supvisors| chooses the node in the ``address_list`` having the lowest
expected *loading*. The aim is to distribute the process loading among the available nodes.

When applying the ``MOST_LOADED`` strategy, with respect of the common rules, |Supvisors| chooses the node in
the ``address_list`` having the greatest expected *loading*.
The aim is to maximize the loading of a node before starting to load another node.
This strategy is more interesting when the resources are limited.

When applying the ``LOCAL`` strategy, |Supvisors| chooses the local node provided that it is compliant
with the ``address_list``. A typical use case is to start an HCI application on a given workstation,
while other applications / services may be distributed over other nodes.

.. attention::

    A consequence of choosing the ``LOCAL`` strategy as the default ``starting_strategy``
    in the :ref:`supvisors_section` is that no process will be started on other node than the *Master* node.


Starting a process
~~~~~~~~~~~~~~~~~~

The internal *Starter* of |Supvisors| applies the following algorithm to start a process:

| if process state is not ``RUNNING``:
|     choose a starting node for the program in accordance with the rules defined above
|     perform a ``supvisors.start_args(namespec)`` XML-RPC to the |Supvisors| instance running on the chosen node
|

This single job is considered completed when:

    * a ``RUNNING`` event is received and the ``wait_exit`` rule is **not** set for this process,
    * an ``EXITED`` event with an expected exit code is received and the ``wait_exit`` rule is set for this process,
    * an error is encountered (``FATAL`` event, ``EXITED`` event with an unexpected exit code),
    * no ``STARTING`` event has been received 5 seconds after the XML-RPC.

This principle is used for starting a single process using a ``supvisors.start_process`` XML-RPC.


Starting an application
~~~~~~~~~~~~~~~~~~~~~~~

The application start sequence is re-evaluated every time a new node becomes active in |Supvisors|. Indeed, as
explained above, the internal data structure is updated with the programs configured in the |Supervisor| instance
of the new node and this new data may have an impact on the application start sequence.

It corresponds to a dictionary where:

    * the keys correspond to the list of ``start_sequence`` values defined in the program rules of the application,
    * the value associated to a key is the list of programs having this key as ``start_sequence``.

.. hint::

    The logic applied here is an answer to the following |Supervisor| unresolved issues:

        * `#122 - supervisord Starts All Processes at the Same Time <https://github.com/Supervisor/supervisor/issues/122>`_
        * `#456 - Add the ability to set different "restart policies" on process workers <https://github.com/Supervisor/supervisor/issues/456>`_

.. note::

    Only the *Managed* applications can have a start sequence, i.e. only those that are declared in the |Supvisors|
    :ref:`rules_file`.

    The programs having a ``start_sequence`` lower or equal to 0 are not considered in the start sequence, as they are
    not meant to be automatically started.

The internal *Starter* of |Supvisors| applies the following principle to start an application:

| while application start sequence is not empty:
|     pop the process list having the lower (strictly positive) ``start_sequence``
|
|     for each process in process list:
|         apply `Starting a process`_
|
|     wait for the jobs to complete
|

This principle is used for starting a single application using a ``supvisors.start_application`` XML-RPC.


Starting all applications
~~~~~~~~~~~~~~~~~~~~~~~~~

When entering the ``DEPLOYMENT`` state, each |Supvisors| instance evaluates the global start sequence using
the ``start_sequence`` rule configured for the applications and processes.

The global start sequence corresponds to a dictionary where:

    * the keys correspond to the list of ``start_sequence`` values defined in the application rules,
    * the value associated to a key is the list of application start sequences whose applications have this key
      as ``start_sequence``.

The |Supvisors| *Master* instance uses the global start sequence to start the applications in the defined order.
The following pseudo-code explains the logic used:

| while global start sequence is not empty:
|     pop the application start sequences having the lower (strictly positive) ``start_sequence``
|
|     while application start sequences are not empty:
|
|         for each sequence in application start sequences:
|             pop the process list having the lower (strictly positive) ``start_sequence``
|
|             for each process in process list:
|                 apply `Starting a process`_
|
|         wait for the jobs to complete
|

.. note::

    The applications having a ``start_sequence`` lower or equal to 0 are not considered,
    as they are not meant to be autostarted.

.. note::

    When leaving the ``DEPLOYMENT`` state, it may happen that some applications are not started properly
    due to missing nodes. When a node is started later and is authorized in the |Supvisors| ensemble,
    |Supvisors| transitions back to the ``DEPLOYMENT`` state to repair such applications.
    May the new node arrive during a ``DEPLOYMENT`` or ``CONCILIATION`` phase, the transition to the ``DEPLOYMENT``
    state is deferred until the current deployment or conciliation jobs are completed.
    It has been chosen NOT to transition back to the ``INITIALIZATION`` state to avoid a new synchronization phase.


.. _starting_failure_strategy:

Starting Failure strategy
-------------------------

When an application is starting, it may happen that any of its programs cannot be started due to various reasons
(the program command line is wrong ; third parties are missing ; none of the nodes defined in the ``address_list``
of the program rules are started ; the applicable nodes are already too much loaded ; etc).

|Supvisors| uses the ``starting_failure_strategy`` option of the rules file to determine the behavior to apply
when a ``required`` program cannot be started. Program having the ``required`` set to False are not considered as
their absence is minor by definition.

Possible values are:

    * ``ABORT``: Abort the application starting.
    * ``STOP``: Stop the application.
    * ``CONTINUE``: Skip the failure and continue the application starting.


.. _running_failure_strategy:

Running Failure strategy
------------------------

The ``autorestart`` option of |Supervisor| may be used to restart automatically a process that has crashed
or has exited unexpectedly (or not). However, when the node itself crashes or becomes unreachable,
the other |Supervisor| instances cannot do anything about that.

|Supvisors| uses the ``running_failure_strategy`` option of the rules file to warm restart a process that was
running on a node that has crashed, in accordance with the default ``starting_strategy`` set in the
:ref:`supvisors_section` and with the ``address_list`` program rules set in the :ref:`rules_file`.

This option can be also used to stop or restart the whole application after a process crash. Indeed, it may happen
that some applications cannot survive if one of their programs is just restarted.

Possible values are:

    * ``CONTINUE``: Skip the failure. The application keeps running.
    * ``RESTART_PROCESS``: Restart the lost process on another node.
    * ``STOP_APPLICATION``: Stop the application.
    * ``RESTART_APPLICATION``: Restart the application.

.. attention::

    The ``RESTART_PROCESS`` is NOT intended to replace the |Supervisor| ``autorestart`` on the local node.
    Provided a program definition where ``autorestart`` is set to ``false`` in the |Supervisor| configuration file
    and where the ``running_failure_strategy`` option is set to ``RESTART_PROCESS`` in the |Supvisors| rules file,
    if the process crashes, |Supvisors| will NOT restart the process.

.. note::

    Given that this option is set on the program rules, program strategies within an application may be incompatible
    in the event of multiple failures. That's why priorities have been set on this strategy.
    ``STOP_APPLICATION`` supersedes ``RESTART_APPLICATION``, which itself supersedes ``RESTART_PROCESS`` and finally
    ``CONTINUE``. So if a program with the ``RESTART_APPLICATION`` option fails at the same time that a program
    of the same application with the ``STOP_APPLICATION`` option, only the ``STOP_APPLICATION`` will be applied.

    When the ``RESTART_PROCESS`` strategy is evaluated, if the application is fully stopped - supposedly because of the
    failure -, |Supvisors| will promote the ``RESTART_PROCESS`` into ``RESTART_APPLICATION``. The idea is to benefit
    from a full start sequence at application level rather than uncorrelated program restarts in the event of multiple
    failures within the same application.

.. hint::

   The ``STOP_APPLICATION`` strategy provides an answer to the following |Supervisor| request:

      * `#874 - Bring down one process when other process gets killed in a group <https://github.com/Supervisor/supervisor/issues/874>`_


.. _stopping_strategy:

Stopping strategy
-----------------

|Supvisors| provides a means to stop a process without telling explicitly where it is running.


Stopping a process
~~~~~~~~~~~~~~~~~~

The internal *Stopper* of |Supvisors| applies the following algorithm to stop a process:

| if process state is ``RUNNING``:
|     perform a ``supervisor.stopProcess(namespec)`` XML-RPC to the |Supervisor| instance where the process is running
|

This single job is considered completed when:

    * a ``STOPPED`` event is received for this process,
    * an error is encountered (``FATAL`` event, ``EXITED`` event whatever the exit code),
    * no ``STOPPING`` event has been received 5 seconds after the XML-RPC.

This principle is used for stopping a single process using a ``supvisors.stop_process`` XML-RPC.


Stopping an application
~~~~~~~~~~~~~~~~~~~~~~~

The application stop sequence is defined at the same moment than the application start sequence.
It corresponds to a dictionary where:

    * the keys correspond to the list of ``stop_sequence`` values defined in the program rules of the application,
    * the value associated to a key is the list of programs having this key as ``stop_sequence``.

.. note::

    The *Unmanaged* applications do have a stop sequence. All their programs have the default ``stop_sequence``
    set to ``0``.

.. hint::

    The logic applied here is an answer to the following |Supervisor| unresolved issue:

        * `#520 - allow a program to wait for another to stop before being stopped? <https://github.com/Supervisor/supervisor/issues/520>`_

.. hint::

    All the programs sharing the same ``stop_sequence`` are stopped simultaneously, which solves some of the requests
    described in the following |Supervisor| unresolved issue:

        * `#723 - Restart waits for all processes to stop before starting any <https://github.com/Supervisor/supervisor/issues/723>`_

The internal *Stopper* of |Supvisors| applies the following algorithm to stop an application:

| while application stop sequence is not empty:
|     pop the process list having the lower ``stop_sequence``
|
|     for each process in process list:
|         apply `Stopping a process`_
|
|     wait for the jobs to complete
|

This principle is used for stopping a single application using a ``supvisors.stop_application`` XML-RPC.


Stopping all applications
~~~~~~~~~~~~~~~~~~~~~~~~~

The applications are stopped when |Supvisors| is requested to restart or shut down.

When entering the ``DEPLOYMENT`` state, each |Supvisors| instance evaluates also the global stop sequence
using the ``stop_sequence`` rule configured for the applications and processes.

The global stop sequence corresponds to a dictionary where:

    * the keys correspond to the list of ``stop_sequence`` values defined in the application rules,
    * the value associated to a key is the list of application stop sequences whose applications have this key
      as ``stop_sequence``.

Upon reception of the ``supvisors.restart`` or ``supvisors.shutdown``, the |Supvisors| instance uses
the global stop sequence to stop all the running applications in the defined order.
The following pseudo-code explains the logic used:

| while global stop sequence is not empty:
|     pop the application stop sequences having the lower ``stop_sequence``
|
|     while application stop sequences are not empty:
|
|         for each sequence in application stop sequences:
|             pop the process list having the lower ``stop_sequence``
|
|             for each process in process list:
|                 apply `Stopping a process`_
|
|         wait for the jobs to complete
|


.. _conciliation:

Conciliation
------------

|Supvisors| is designed so that there should be only one instance of the same program running on a set of systems,
although all of them may have the capability to start it.

Nevertheless, it is still likely to happen in a few cases:

    * using a request to |Supervisor| itself (through Web UI, :program:`supervisorctl`, XML-RPC),
    * upon a network failure.

.. attention::

    In the case of a network failure, as described in :ref:`auto_fencing`, and if the ``auto_fence`` option is not set,
    the Address is set to ``SILENT`` instead of ``ISOLATED`` and its URL is not disconnected from the subscriber socket.

    When the network failure is fixed, |Supvisors| has likely to deal with a duplicated list of applications
    and processes.

When such a conflict is detected, |Supvisors| enters in the ``CONCILIATION`` state.
Depending on the ``conciliation_strategy`` option set in the :ref:`supvisors_section`, it applies a strategy to be rid
of all duplicates:

``SENICIDE``

    When applying the ``SENICIDE`` strategy, |Supvisors| keeps the youngest process, i.e. the process that has been
    started the most recently, and stops all the others.

``INFANTICIDE``

    When applying the ``INFANTICIDE`` strategy, |Supvisors| keeps the oldest process and stops all the others.

``USER``

    That's the easy one. When applying the ``USER`` strategy, |Supvisors| just waits for an user application
    to solve the conflicts using Web UI, :program:`supervisorctl`, XML-RPC, process signals, or any other solution.

``STOP``

    When applying the ``STOP`` strategy, |Supvisors| stops all conflicting processes, which may lead
    the corresponding applications to a degraded state.

``RESTART``

    When applying the ``RESTART`` strategy, |Supvisors| stops all conflicting processes and restarts a new one.

``RUNNING_FAILURE``

    When applying the ``RUNNING_FAILURE`` strategy, |Supvisors| stops all conflicting processes and deals
    with the conflict as it would deal with a running failure, depending on the strategy defined for the process.
    So, after the conflicting processes are all stopped, |Supvisors| may restart the process, stop the application,
    restart the application or do nothing at all.

|Supvisors| leaves the ``CONCILIATION`` state when all conflicts are conciliated.

.. include:: common.rst
