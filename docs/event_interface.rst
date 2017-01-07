Event interface
===============

Protocol
--------

The Supvisors Event Interface relies on a ZeroMQ socket.
To receive the Supvisors events, the client application must configure a socket with a SUBSCRIBE pattern and connect it on localhost using the event_port defined in the supvisors section of the Supervisor configuration file.

Supvisors publishes the events in multi-parts messages.

Message header
--------------

The first part is a header that consists in an unicode string. This header identifies the type of the event, defined as follows in the supvisors.utils module:

SUPVISORS_STATUS_HEADER = u'supvisors'
ADDRESS_STATUS_HEADER = u'address'
APPLICATION_STATUS_HEADER = u'application'
PROCESS_STATUS_HEADER = u'process'

ZeroMQ makes it possible to filter the messages received on the client side by subcribing to a part of them.
To receive all messages, just subscribe using an empty string.
For example, the following lines in python configure the ZMQ socket so as to receive only the SupvisorsStatus and ProcessStatus events:

socket.setsockopt(zmq.SUBSCRIBE, SUPVISORS_STATUS_HEADER.encode('utf-8'))
socket.setsockopt(zmq.SUBSCRIBE, PROCESS_STATUS_HEADER.encode('utf-8'))

Message data
------------

The second part of the message is a dictionary serialized in JSON. Of course, the contents depends on the message type.

Supvisors status
~~~~~~~~~~~~~~~~

Supvisors Status Dictionary Key	Value
'statecode'	The state of Supvisors, in [0;3].
'statename'	The state of Supvisors, among { 'INITIALIZATION', 'DEPLOYMENT', 'OPERATION', 'CONCILIATION' }.

Address status
~~~~~~~~~~~~~~

Address Status Dictionary Key	Value
'address_name'	Name of the address.
'statecode'	State of the address, in [0;4].
'state'name	State of the address, among { 'UNKNOWN', 'CHECKING', 'RUNNING', 'SILENT', 'ISOLATING', 'ISOLATED' }.
'remote_time'	Date of the last TICK event received from this address.
'local_time'	Local date of the last TICK event received from this address.
'loading'	Sum of the expected loading of the processes running on the address.

Application status
~~~~~~~~~~~~~~~~~~

Application Status Dictionary Key	Value
'application_name'	Name of the application.
'statecode'	State of the application, in [0;4].
'statename'	State of the application, among { 'STOPPED', 'STARTING', 'RUNNING', 'STOPPING' }.
'major_failure'	True if the application is running and at least one required process is not started.
'minor_failure'	True if the application is running and at least one optional (not required) process is not started.

Process status
~~~~~~~~~~~~~~

Process Status Dictionary Key	Value
'application_name'	Name of the application.
'process_name'	Name of the process.
'statecode'	State of the process, in {0, 10, 20, 30, 40, 100, 200, 1000}.
'statename'	State of the process, among { 'STOPPED', 'STARTING', 'RUNNING', 'BACKOFF', 'STOPPING', 'EXITED', 'FATAL', 'UNKNOWN' }.
'expected_exit'	True if the exit status is expected (only when state is 'EXITED').
'last_event_time'	Date of the last process event received for this process, regardless of the origin (Supervisor instance).
'addresses'	List of addresses where the process is running.

Event Clients
-------------

This section explains how to use receive the Supvisors Events from a Python, JAVA or C++ client.

Python Client
~~~~~~~~~~~~~

The SupvisorsEventInterface of the supvisors.client.subscriber module is designed to receive the Supvisors events from the local Supvisors instance.
The default behaviour is to print the messages received. For any other behaviour, just specialize the methods on_xxx_status of the class SupvisorsEventInterface.
No additional third party is required.

.. code-block:: python

    from supvisors.client.subscriber import *

    # create the subscriber thread
    subscriber = SupvisorsEventInterface(create_zmq_context(), port, create_logger())
    # subscribe to all messages
    subscriber.subscribe_all()
    # start the thread
    subscriber.start()

JAVA Client
~~~~~~~~~~~

Supvisors provides a JAVA client in the client/java directory of the Supvisors installation directory.

The SupvisorsEventSubscriber of the org.supvisors.event package is designed to receive the Supvisors events from the local Supvisors instance.
A SupvisorsEventListener with a specialization of the methods onXxxStatus must be attached to the SupvisorsEventSubscriber instance to receive the notifications.
It requires the following additional dependencies:

    * JeroMQ.
    * JSON-java.

The binary JAR of JeroMQ 0.3.6 is available in the MAVEN repository.

The binary JAR of JSON-java 20160810 is available in the MAVEN repository.

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
    });

    // start subscriber in thread
    Thread t = new Thread(subscriber);
    t.start();

C++ Client
~~~~~~~~~~

Not implemented yet

