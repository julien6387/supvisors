.. _event_interface:

Event interface
===============

Protocol
--------

The |Supvisors| Event Interface relies on a PyZMQ_ socket.
To receive the |Supvisors| events, the client application must configure a socket with a ``SUBSCRIBE`` pattern
and connect it on localhost using the ``event_port`` option defined in the :ref:`supvisors_section` of the |Supervisor|
configuration file. The ``event_link`` option must also be set to ``ZMQ``.

|Supvisors| publishes the events in multi-parts messages.


Message header
--------------

The first part is a header that consists in an unicode string. This header identifies the type of the event,
defined as follows in the ``supvisors.ttypes`` module:

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


PyZMQ_ makes it possible to filter the messages received on the client side by subscribing to a part of them.
To receive all messages, just subscribe using an empty string.
For example, the following lines in python configure the PyZMQ_ socket so as to receive only the ``Supvisors``
and ``Process`` events:

.. code-block:: python

    socket.setsockopt(zmq.SUBSCRIBE, EventHeaders.SUPVISORS.value.encode('utf-8'))
    socket.setsockopt(zmq.SUBSCRIBE, EventHeaders.PROCESS_STATUS.value.encode('utf-8'))


Message data
------------

The second part of the message is a dictionary serialized in ``JSON``.
Of course, the contents depends on the message type.


|Supvisors| status
~~~~~~~~~~~~~~~~~~

================== ================= ==================
Key	               Type               Value
================== ================= ==================
'fsm_statecode'    ``int``           The state of |Supvisors|, in [0;6].
'fsm_statename'    ``str``           The string state of |Supvisors|, among { ``'INITIALIZATION'``, ``'DEPLOYMENT'``,
                                     ``'OPERATION'``, ``'CONCILIATION'``, ``'RESTARTING'``, ``'SHUTTING_DOWN'``,
                                     ``'SHUTDOWN'`` }.
'starting_jobs'    ``list(str)``     The list of |Supvisors| instances having starting jobs in progress.
'stopping_jobs'    ``list(str)``     The list of |Supvisors| instances having stopping jobs in progress.
================== ================= ==================


|Supvisors| instance status
~~~~~~~~~~~~~~~~~~~~~~~~~~~

================== ================= ==================
Key	               Type              Value
================== ================= ==================
'identifier'       ``str``           The deduced name of the |Supvisors| instance.
'node_name'        ``str``           The name of the node where the |Supvisors| instance is running.
'port'             ``int``           The HTTP port of the |Supvisors| instance.
'statecode'        ``int``           The |Supvisors| instance state, in [0;5].
'statename'        ``str``           The |Supvisors| instance state as string, among { ``'UNKNOWN'``, ``'CHECKING'``,
                                     ``'RUNNING'``, ``'SILENT'``, ``'ISOLATING'``, ``'ISOLATED'`` }.
'sequence_counter' ``int``           The TICK counter, i.e. the number of Tick events received since it is running.
'remote_time'      ``float``         The date of the last ``TICK`` event received from this node, in ms.
'local_time'       ``float``         The local date of the last ``TICK`` event received from this node, in ms.
'loading'          ``int``           The sum of the expected loading of the processes running on the node, in [0;100]%.
'process_failure'  ``bool``          True if one of the local processes has crashed or has exited unexpectedly.
================== ================= ==================


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
'identifiers'      ``list(str)``     The deduced names of the |Supvisors| instances where the process is running.
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
'now'              ``float``         The date of the event in the reference time of the node.
'pid'              ``int``           The UNIX process ID (only when state is 20 - ``RUNNING`` or 40 - ``STOPPING``).
'identifier'       ``str``           The deduced name of the |Supvisors| instance that sent the initial event.
'extra_args'       ``str``           The additional arguments passed to the command line of the process.
'disabled'         ``bool``          True if the process is disabled on the |Supvisors| instance.
================== ================= ==================


Host statistics
~~~~~~~~~~~~~~~

================== ========================= ==================
Key                Type                      Value
================== ========================= ==================
'identifier'       ``str``                   The deduced name of the |Supvisors| instance.
'target_period'    ``float``                 The configured integration period.
'period'           ``list(float)``           The start and end uptimes of the integration period, as a list of 2 values.
'cpu'              ``list(float)``           The CPU (IRIX mode) on the node.
                                             The first element of the list is the average CPU.
                                             The following elements correspond to the CPU on every processor core.
'mem'              ``float``                 The memory occupation on the node.
'io'               ``dict(str,list(float)``  The Process namespec.
================== ========================= ==================


Process statistics
~~~~~~~~~~~~~~~~~~

================== ================= ==================
Key                Type              Value
================== ================= ==================
'namespec'         ``str``           The Process namespec.
'identifier'       ``str``           The deduced name of the |Supvisors| instance.
'target_period'    ``float``         The configured integration period.
'period'           ``list(float)``   The start and end uptimes of the integration period, as a list of 2 values.
'cpu'              ``float``         The CPU (IRIX mode) of the process on the node.
'mem'              ``float``         The memory occupation of the process on the node.
================== ================= ==================


Event Clients
-------------

This section explains how to use receive the |Supvisors| Events from a Python or JAVA client.


Python Client
~~~~~~~~~~~~~

The *SupvisorsZmqEventInterface* is designed to receive the |Supvisors| events from the local |Supvisors| instance.
It requires PyZmq_ to be installed.


.. automodule:: supvisors.client.zmqsubscriber

  .. autoclass:: SupvisorsZmqEventInterface

       .. automethod:: on_supvisors_status(data)
       .. automethod:: on_instance_status(data)
       .. automethod:: on_application_status(data)
       .. automethod:: on_process_status(data)
       .. automethod:: on_process_event(data)

.. code-block:: python

    from supvisors.client.zmqsubscriber import *

    # create the subscriber thread
    subscriber = SupvisorsZmqEventInterface(zmq.Context.instance(), port, create_logger())
    # subscribe to all messages
    subscriber.subscribe_all()
    # start the thread
    subscriber.start()


JAVA Client
~~~~~~~~~~~

Each |Supvisors| release includes a JAR file that contains a JAVA client.
It can be downloaded from the `Supvisors releases <https://github.com/julien6387/supvisors/releases>`_.

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
    SupvisorsEventSubscriber subscriber = new SupvisorsEventSubscriber(60002, context);
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
    });

    // start subscriber in thread
    Thread t = new Thread(subscriber);
    t.start();

.. include:: common.rst
