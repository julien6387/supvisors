.. _event_interface:

Event interface
===============

Available Protocols
-------------------

The |Supvisors| Event Interface can be created either using a |ZeroMQ| socket or using |websockets|.

All messages consist in a header and a body.

.. attention::

    The |websockets| implementation requires a :command:`Python` version 3.7 or later.

Message header
--------------

This header is a unicode string that identifies the type of the event and that is defined as follows
in the ``supvisors.ttypes`` module:

.. code-block:: python

    class EventHeaders(Enum):
        """ Strings used as headers in messages between EventPublisher and Supvisors' Client. """
        SUPVISORS = 'supvisors'
        INSTANCE = 'instance'
        APPLICATION = 'application'
        PROCESS_EVENT = 'event'
        PROCESS_STATUS = 'process'
        HOST_STATISTICS = 'hstats'
        PROCESS_STATISTICS = 'pstats'

The header value is used to set the event subscriptions.

Message data
------------

The second part of the message is a dictionary serialized in ``JSON``.
Of course, the contents depends on the message type.


|Supvisors| status
~~~~~~~~~~~~~~~~~~

=================== ================= ==================
Key	                Type               Value
=================== ================= ==================
'identifier'        ``str``           The identifier of the |Supvisors| instance.
'nick_identifier'   ``str``           The |Supvisors| instance nick name, as set in the ``supvisors_list`` option,
                                      or a copy of the |Supvisors| identifier if not set.
'fsm_statecode'     ``int``           The state of |Supvisors|, in [0;7].
'fsm_statename'     ``str``           The string state of |Supvisors|, among { ``'SYNCHRONIZATION'``, ``'ELECTION'``,
                                      ``'DISTRIBUTION'``, ``'OPERATION'``, ``'CONCILIATION'``, ``'RESTARTING'``,
                                      ``'SHUTTING_DOWN'``, ``'FINAL'`` }.
'master_identifier' ``str``           The identifier of the |Supvisors| *Master* instance.
'degraded_mode'     ``bool``          True if |Supvisors| is working with missing |Supvisors| instances.
'discovery_mode'    ``bool``          True if the |Supvisors| discovery mode is activated.
'starting_jobs'     ``list(str)``     The list of |Supvisors| instances having starting jobs in progress.
'stopping_jobs'     ``list(str)``     The list of |Supvisors| instances having stopping jobs in progress.
'instance_states'   ``dict(str,str)`` The state of every |Supvisors| instance, as seen by the local |Supvisors|
                                      instance.
=================== ================= ==================


|Supvisors| instance status
~~~~~~~~~~~~~~~~~~~~~~~~~~~

========================= ========== ==================
Key	                      Type       Value
========================= ========== ==================
'identifier'              ``str``    The identifier of the |Supvisors| instance.
'nick_identifier'         ``str``    The |Supvisors| instance nick name, as set in the ``supvisors_list`` option,
                                     or a copy of the |Supvisors| identifier if not set.
'node_name'               ``str``    The name of the node where the |Supvisors| instance is running.
'port'                    ``int``    The HTTP port of the |Supvisors| instance.
'statecode'               ``int``    The |Supvisors| instance state, in [0;5].
'statename'               ``str``    The |Supvisors| instance state as string, among { ``'STOPPED'``, ``'CHECKING'``,
                                     `'CHECKED'``, ``'RUNNING'``, ``'FAILED'``, ``'ISOLATED'`` }.
'remote_sequence_counter' ``int``    The remote TICK counter, i.e. the number of TICK events received since
                                     the remote |Supvisors| instance is running.
'remote_mtime'            ``float``  The monotonic time received in the last heartbeat sent by the remote
                                     |Supvisors| instance, in seconds since the remote host started.
'remote_time'             ``float``  The POSIX time received in the last heartbeat sent by the remote
                                     |Supvisors| instance, in seconds and in the remote reference time.
'local_sequence_counter'  ``int``    The local TICK counter when the latest TICK was received from the remote
                                     |Supvisors| instance.
'local_mtime'             ``float``  The monotonic time when the latest TICK was received from the remote
                                     |Supvisors| instance, in seconds since the local host started.
'local_time'              ``float``  The POSIX time when the latest TICK was received from the remote
                                     |Supvisors| instance, in seconds and in the local reference time.
'loading'                 ``int``    The sum of the expected loading of the processes running on the node, in [0;100]%.
'process_failure'         ``bool``   True if one of the local processes has crashed or has exited unexpectedly.
========================= ========== ==================


Application status
~~~~~~~~~~~~~~~~~~

================== ================= ==================
Key	               Type              Value
================== ================= ==================
'application_name' ``str``           The Application name.
'statecode'        ``int``           The Application state, in [0;3].
'statename'        ``str``           The Application state as string, among { ``'STOPPED'``, ``'STARTING'``,
                                     ``'RUNNING'``, ``'STOPPING'`` }.
'major_failure'    ``bool``          True if the application is running and at least one required process is not started.
'minor_failure'    ``bool``          True if the application is running and at least one optional (not required) process
                                     is not started.
================== ================= ==================


Process status
~~~~~~~~~~~~~~

================== ================= ==================
Key	               Type              Value
================== ================= ==================
'application_name' ``str``           The Application name.
'process_name'     ``str``           The Process name.
'statecode'        ``int``           The Process state, in {0, 10, 20, 30, 40, 100, 200, 1000}.
                                     A special value -1 means that the process has been deleted as a consequence
                                     of an XML-RPC ``update_numprocs``.
'statename'        ``str``           The Process state as string, among { ``'STOPPED'``, ``'STARTING'``, ``'RUNNING'``,
                                     ``'BACKOFF'``, ``'STOPPING'``, ``'EXITED'``, ``'FATAL'``, ``'UNKNOWN'`` }.
                                     A special value ``DELETED`` means that the process has been deleted as a consequence
                                     of an XML-RPC ``update_numprocs``.
'expected_exit'    ``bool``          True if the exit status is expected (only when state is ``'EXITED'``).
'last_event_time'  ``float``         The date of the last process event received for this process, regardless
                                     of the originating |Supvisors| instance.
'identifiers'      ``list(str)``     The identifiers of the |Supvisors| instances where the process is running.
'extra_args'       ``str``           The additional arguments passed to the command line of the process.
================== ================= ==================

.. hint::

    The ``expected_exit`` information of this event provides an answer to the following |Supervisor| request:

        * `#1150 - Why do event listeners not report the process exit status when stopped/crashed?
          <https://github.com/Supervisor/supervisor/issues/1150>`_

Process event
~~~~~~~~~~~~~

================== ================= ==================
Key                Type              Value
================== ================= ==================
'group'            ``str``           The Application name.
'name'             ``str``           The Process name.
'state'            ``int``           The Process state, in {0, 10, 20, 30, 40, 100, 200, 1000}.
                                     A special value -1 means that the process has been deleted as a consequence
                                     of an XML-RPC ``update_numprocs``.
'expected'         ``bool``          True if the exit status is expected (only when state is 100 - ``EXITED``).
'now'              ``float``         The monotonic time of the event in the reference time of the host.
'pid'              ``int``           The UNIX process ID (only when state is 20 - ``RUNNING`` or 40 - ``STOPPING``).
'identifier'       ``str``           The identifier of the |Supvisors| instance that sent the initial event.
'extra_args'       ``str``           The additional arguments passed to the command line of the process.
'disabled'         ``bool``          True if the process is disabled on the |Supvisors| instance.
================== ================= ==================


Host statistics
~~~~~~~~~~~~~~~

================== ========================= ==================
Key                Type                      Value
================== ========================= ==================
'identifier'       ``str``                   The identifier of the |Supvisors| instance.
'target_period'    ``float``                 The configured integration period, in seconds.
'period'           ``list(float)``           The start and end uptimes of the integration period, as a list of 2 values
                                             in seconds.
'cpu'              ``list(float)``           The CPU (IRIX mode) on the node, in percent.
                                             The first element of the list is the average CPU.
                                             The following elements correspond to the CPU on every processor core.
'mem'              ``float``                 The memory occupation on the node, in percent.
'net_io'           ``dict(str, list(float)`` The received and sent bytes per network interface.
'disk_io'          ``dict(str, list(float)`` The read and written bytes per physical device.
'disk_usage'       ``dict(str, float)``      The usage per physical partition, in percent.
================== ========================= ==================


Process statistics
~~~~~~~~~~~~~~~~~~

================== ================= ==================
Key                Type              Value
================== ================= ==================
'namespec'         ``str``           The Process namespec.
'identifier'       ``str``           The identifier of the |Supvisors| instance.
'target_period'    ``float``         The configured integration period, in seconds.
'period'           ``list(float)``   The start and end uptimes of the integration period, as a list of 2 values in seconds.
'cpu'              ``float``         The CPU (IRIX mode) of the process on the node, in percent.
'mem'              ``float``         The memory occupation of the process on the node, in percent.
================== ================= ==================


|ZeroMQ| Implementation
-----------------------

The |ZeroMQ| implementation relies on a ``PUB-SUB`` pattern provided by |PyZMQ| (:command:`Python` binding of |ZeroMQ|).

When the ``event_link`` option is set to ``ZMQ``, |Supvisors| binds a ``PUBLISH`` |PyZMQ| socket on all interfaces
using the ``event_port`` option defined in the :ref:`supvisors_section` of the |Supervisor| configuration file.

|Supvisors| publishes the events in multi-parts messages.
The first part is the message header, as a unicode string. The body follows, encoded in JSON.

To receive the |Supvisors| events, the client application must connect a ``SUBSCRIBE`` |PyZMQ| socket to the address
defined by the node name and the port number where the |Supvisors| ``PUBLISH`` |PyZMQ| socket is bound.

|PyZMQ| makes it possible to filter the messages received on the client side by subscribing to a part of them.
To receive all messages, just subscribe using an empty string.

For example, the following :command:`Python` instructions configure the |PyZMQ| socket so as to receive only
the *Supvisors Status* and *Process Status* events:

.. code-block:: python

    socket.setsockopt(zmq.SUBSCRIBE, EventHeaders.SUPVISORS.value.encode('utf-8'))
    socket.setsockopt(zmq.SUBSCRIBE, EventHeaders.PROCESS_STATUS.value.encode('utf-8'))


Python Client
~~~~~~~~~~~~~

|Supvisors| provides a :command:`Python` implementation of the |ZeroMQ| client subscriber.
The *SupvisorsZmqEventInterface* is designed to receive the |Supvisors| events from a |Supvisors| instance.
It requires |PyZMQ| to be installed.


.. automodule:: supvisors.client.zmqsubscriber

  .. autoclass:: SupvisorsZmqEventInterface

       .. automethod:: on_supvisors_status(data)
       .. automethod:: on_instance_status(data)
       .. automethod:: on_application_status(data)
       .. automethod:: on_process_status(data)
       .. automethod:: on_process_event(data)
       .. automethod:: on_host_statistics(data)
       .. automethod:: on_process_statistics(data)

.. code-block:: python

    import zmq.asyncio
    from supvisors.client.clientutils import create_logger
    from supvisors.client.zmqsubscriber import SupvisorsZmqEventInterface

    # create the subscriber thread
    subscriber = SupvisorsZmqEventInterface(zmq.asyncio.Context.instance(), 'localhost', 9003, create_logger())
    # subscribe to all messages
    subscriber.subscribe_all()
    # start the thread
    subscriber.start()


JAVA Client
~~~~~~~~~~~

A :command:`JAVA` implementation of the |ZeroMQ| client subscriber is made available with each |Supvisors| release
through a JAR file. This file can be downloaded from the `Supvisors releases <https://github.com/julien6387/supvisors/releases>`_.

The *SupvisorsEventSubscriber* of the ``org.supvisors.event package`` is designed to receive the |Supvisors| events
from the local |Supvisors| instance.
A *SupvisorsEventListener* with a specialization of the methods ``onXxxStatus`` must be attached to
the *SupvisorsEventSubscriber* instance to receive the notifications.

It requires the following additional dependencies:

    * `JeroMQ <https://github.com/zeromq/jeromq>`_.
    * `Gson <https://github.com/google/gson>`_.

The binary JAR of :program:`JeroMQ 0.5.2` is available in the
`JeroMQ MAVEN repository <https://mvnrepository.com/artifact/org.zeromq/jeromq/0.5.2>`_.

The binary JAR of :program:`Google Gson 2.8.6` is available in the
`Gson MAVEN repository <https://mvnrepository.com/artifact/com.google.code.gson/gson/2.8.6>`_.

.. code-block:: java

    import org.supvisors.event.*;

    // create ZeroMQ context
    Context context = ZMQ.context(1);

    // create and configure the subscriber
    SupvisorsEventSubscriber subscriber = new SupvisorsEventSubscriber(9003, context);
    subscriber.subscribeToAll();
    subscriber.setListener(new SupvisorsEventListener() {

        @Override
        public void onSupvisorsStatus(final SupvisorsStatus status) {
            System.out.println(status);
        }

        @Override
        public void onInstanceStatus(final SupvisorsInstanceInfo status) {
            System.out.println(status);
        }

        @Override
        public void onApplicationStatus(final SupvisorsApplicationInfo status) {
            System.out.println(status);
        }

        @Override
        public void onProcessStatus(final SupvisorsProcessInfo status) {
            System.out.println(status);
        }

        @Override
        public void onProcessEvent(final SupvisorsProcessEvent event) {
            System.out.println(event);
        }

        @Override
        public void onHostStatistics(final SupvisorsHostStatistics status) {
            System.out.println(status);
        }

        @Override
        public void onProcessStatistics(final SupvisorsProcessStatistics status) {
            System.out.println(status);
        }
    });

    // start subscriber in thread
    Thread t = new Thread(subscriber);
    t.start();


|websockets| Implementation
---------------------------

.. attention::

    The |websockets| implementation requires a :command:`Python` version 3.7 or later.

When the ``event_link`` option is set to ``WS``, |Supvisors| creates a |websockets| server that binds on all interfaces
using the ``event_port`` option defined in the :ref:`supvisors_section` of the |Supervisor| configuration file.

|Supvisors| publishes the event messages as a tuple of header, as a unicode string, and body, encoded in JSON.

To receive the |Supvisors| events, the client application must create a |websockets| client that connects
to the address defined by the node name and the port number where the |Supvisors| |websockets| server has bound.

Filtering the messages is performed by adding headers to the path of the URI.
To receive all messages, just add ``all`` to the path of the URI.

For example, the following :command:`Python` instructions configure the |websockets| client so as to receive only
the *Supvisors Status* and *Process Status* events:

.. code-block:: python

    import websockets

    uri = 'ws://localhost:9003/supvisors/process'
    async with websockets.connect(uri) as ws:
        ...


Python Client
~~~~~~~~~~~~~

|Supvisors| provides a :command:`Python` implementation of the |websockets| client.
The *SupvisorsWsEventInterface* is designed to receive the |Supvisors| events from a |Supvisors| instance.
It requires |websockets| to be installed.


.. automodule:: supvisors.client.wssubscriber

  .. autoclass:: SupvisorsWsEventInterface

       .. automethod:: on_supvisors_status(data)
       .. automethod:: on_instance_status(data)
       .. automethod:: on_application_status(data)
       .. automethod:: on_process_status(data)
       .. automethod:: on_process_event(data)
       .. automethod:: on_host_statistics(data)
       .. automethod:: on_process_statistics(data)

.. code-block:: python

    from supvisors.client.clientutils import create_logger
    from supvisors.client.wssubscriber import SupvisorsWsEventInterface

    # create the subscriber thread
    subscriber = SupvisorsWsEventInterface('localhost', 9003, create_logger())
    # subscribe to all messages
    subscriber.subscribe_all()
    # start the thread
    subscriber.start()


.. include:: common.rst
