.. _event_interface:

Event interface
===============

Protocol
--------

The |Supvisors| Event Interface relies on a PyZMQ_ socket.
To receive the |Supvisors| events, the client application must configure a socket with a ``SUBSCRIBE`` pattern
and connect it on localhost using the ``event_port`` defined in the :ref:`supvisors_section`
of the |Supervisor| configuration file.

|Supvisors| publishes the events in multi-parts messages.


Message header
--------------

The first part is a header that consists in an unicode string. This header identifies the type of the event,
defined as follows in the ``supvisors.utils`` module:

.. code-block:: python

    SUPVISORS_STATUS_HEADER = u'supvisors'
    ADDRESS_STATUS_HEADER = u'address'
    APPLICATION_STATUS_HEADER = u'application'
    PROCESS_STATUS_HEADER = u'process'
    PROCESS_EVENT_HEADER = u'event'

PyZMQ_ makes it possible to filter the messages received on the client side by subscribing to a part of them.
To receive all messages, just subscribe using an empty string.
For example, the following lines in python configure the PyZMQ_ socket so as to receive only the ``Supvisors``
and ``Process`` events:

.. code-block:: python

    socket.setsockopt(zmq.SUBSCRIBE, SUPVISORS_STATUS_HEADER.encode('utf-8'))
    socket.setsockopt(zmq.SUBSCRIBE, PROCESS_STATUS_HEADER.encode('utf-8'))


Message data
------------

The second part of the message is a dictionary serialized in ``JSON``.
Of course, the contents depends on the message type.


|Supvisors| status
~~~~~~~~~~~~~~~~~~

================== ==================
Key	               Value
================== ==================
'statecode'        The state of |Supvisors|, in [0;6].
'statename'        The string state of |Supvisors|, among { ``'INITIALIZATION'``, ``'DEPLOYMENT'``, ``'OPERATION'``,
                   ``'CONCILIATION'``, ``'RESTARTING'``, ``'SHUTTING_DOWN'``, ``'SHUTDOWN'`` }.
================== ==================


Address status
~~~~~~~~~~~~~~

================== ==================
Key	               Value
================== ==================
'address_name'     The Address name.
'statecode'        The Address state, in [0;5].
'statename'        The Address state as string, among { ``'UNKNOWN'``, ``'CHECKING'``, ``'RUNNING'``, ``'SILENT'``,
                   ``'ISOLATING'``, ``'ISOLATED'`` }.
'remote_time'      The date of the last ``TICK`` event received from this node, in ms.
'local_time'       The local date of the last ``TICK`` event received from this node, in ms.
'loading'          The sum of the expected loading of the processes running on the node, in [0;100]%.
================== ==================


Application status
~~~~~~~~~~~~~~~~~~

================== ==================
Key	               Value
================== ==================
'application_name' The Application name.
'statecode'        The Application state, in [0;3].
'statename'        The Application state as string, among { ``'STOPPED'``, ``'STARTING'``, ``'RUNNING'``,
                   ``'STOPPING'`` }.
'major_failure'    True if the application is running and at least one required process is not started.
'minor_failure'    True if the application is running and at least one optional (not required) process is not started.
================== ==================


Process status
~~~~~~~~~~~~~~

================== ==================
Key	               Value
================== ==================
'application_name' The Application name.
'process_name'     The Process name.
'statecode'        The Process state, in {0, 10, 20, 30, 40, 100, 200, 1000}. A special value -1 means that the process
                   has been deleted as a consequence of an XML-RPC ``update_numprocs``.
'statename'        The Process state as string, among { ``'STOPPED'``, ``'STARTING'``, ``'RUNNING'``, ``'BACKOFF'``,
                   ``'STOPPING'``, ``'EXITED'``, ``'FATAL'``, ``'UNKNOWN'`` }. A special value ``DELETED`` means that
                   the process has been deleted as a consequence of an XML-RPC ``update_numprocs``.
'expected_exit'    True if the exit status is expected (only when state is ``'EXITED'``).
'last_event_time'  The date of the last process event received for this process, regardless of the originating
                   |Supvisors| instance.
'addresses'        The list of nodes where the process is running.
'extra_args'       The additional arguments passed to the command line of the process.
================== ==================

.. hint::

    The ``expected_exit`` information of this event provides an answer to the following |Supervisor| request:

        * `#1150 - Why do event listeners not report the process exit status when stopped/crashed? <https://github.com/Supervisor/supervisor/issues/1150>`_

Process event
~~~~~~~~~~~~~

================== ==================
Key                Value
================== ==================
'group'            The Application name.
'name'             The Process name.
'state'            The Process state, in {0, 10, 20, 30, 40, 100, 200, 1000}. A special value -1 means that the process
                   has been deleted as a consequence of an XML-RPC ``update_numprocs``.
'expected'         True if the exit status is expected (only when state is 100 - ``EXITED``).
'now'              The date of the event in the reference time of the node.
'pid'              The UNIX process ID (only when state is 20 - ``RUNNING`` or 40 - ``STOPPING``).
'address'          The node where the event comes from.
'extra_args'       The additional arguments passed to the command line of the process.
================== ==================


Event Clients
-------------

This section explains how to use receive the |Supvisors| Events from a Python or JAVA client.


Python Client
~~~~~~~~~~~~~

The *SupvisorsEventInterface* is designed to receive the |Supvisors| events from the local |Supvisors| instance.
No additional third party is required.


.. automodule:: supvisors.client.subscriber

  .. autoclass:: SupvisorsEventInterface

       .. automethod:: on_supvisors_status(data)
       .. automethod:: on_address_status(data)
       .. automethod:: on_application_status(data)
       .. automethod:: on_process_status(data)
       .. automethod:: on_process_event(data)

.. code-block:: python

    from supvisors.client.subscriber import *

    # create the subscriber thread
    subscriber = SupvisorsEventInterface(zmq.Context.instance(), port, create_logger())
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
        public void onAddressStatus(final SupvisorsAddressInfo status) {
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
