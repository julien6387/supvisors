.. _xml_rpc:

XML-RPC API
===========

The Supvisors XML-RPC API is an extension of the Supervisor API.
Detailed information can be found in the Supervisor XML-RPC API Documentation.

The supvisors namespace has been added to the supervisord XML-RPC interface.

The XML-RPC system.listMethods API now provides the list of methods supported for both Supervisor and Supvisors.
An example is provided below.

.. code-block:: python

    server.supvisors.getState()

In the following, the namespec refers to the full name of the process, including the application name.
In some cases, it can also refer to all the programs of the group: X11:\*.

For example: X11:xclock, where 'X11' is the name of a Supervisor group and 'xclock' is the name of a Supervisor program that is referenced in the group.


.. _xml_rpc_status:

Status
------

get_api_version()
    Return the version of the RPC API used by Supvisors
    @return string: the version id

get_supvisors_state()
    Return the state of Supvisors
    @return struct: a structure containing data about the Supvisors state
    Key	Type	Validity	Description
    'statecode'	int	[0;3]	The state of Supvisors.
    'statename'	str	'INITIALIZATION'
    'DEPLOYMENT'
    'OPERATION'
    'CONCILIATION'
    'RESTARTING'
    'SHUTTING_DOWN'
    'SHUTDOWN'	The string state of Supvisors.

get_master_address()
    Return the address of the Supvisors Master
    @return string: the IPv4 address or host name

get_address_info(address)
    Return information about a remote supervisord managed in Supvisors and running on address
    @param string address: the address of the Supvisors instance
    @throws RPCError: with code Faults.BAD_ADDRESS if address is unknown to Supvisors 
    @return struct: a structure containing data about the Supvisors instances
    Key	Type	Unit	Validity	Description
    'address_name'	str			Address of the Supvisors instance.
    'statecode'	int		[0;5]	State of the Supvisors instance.
    'statename'	str		'UNKNOWN'
    'CHECKING'
    'RUNNING'
    'SILENT'
    'ISOLATING'
    'ISOLATED'	State of the Supvisors instance.
    'remote_time'	int	ms		Date of the last heartbeat received from the Supvisors instance, in the remote reference time.
    'local_time'	int	ms		Date of the last heartbeat received from the Supvisors instance, in the local reference time.
    'loading'	int	%	[0;100]	Sum of the expected loading of the processes running on the address.

get_all_addresses_info()
    Return information about all remote supervisord managed in Supvisors
    @return list: a list of structures containing data about all remote Supvisors instances

get_application_info(application_name)
    Return information about the application named application_name
    @param string application_name: the name of the application
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION
        * with code Faults.BAD_NAME if application_name is unknown to Supvisors

    @return struct: a structure containing data about the application
    Key	Type	Unit	Validity	Description
    'application_name'	str			Name of the application.
    'statecode'	int		[0;4]	State of the application.
    'statename'	str		'UNKNOWN'
    'STOPPED'
    'STARTING'
    'STOPPING'
    'RUNNING'	State of the application, as string.
    'major_failure'	bool			True if at least one required process is not started.
    'minor_failure'	bool			True if at least one optional process could not be started.

get_all_applications_info()
    Return information about all applications managed in Supvisors.
    @throws RPCError: with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION.
    @return list: a list of structures containing data about all applications.

get_process_info(namespec)
    Return information about the process named namespec.
    It is a complement of supervisor ProcessInfo by telling where the process is running.
    @param string namespec: the process name (or 'group:name', or 'group:\*').
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION,
        * with code Faults.BAD_NAME if namespec is unknown to Supvisors.

    @return list: a list of structures containing data about the processes.
    Key	Type	Unit	Validity	Description
    'application_name'	str			Name of the process' application.
    'process_name'	str			Name of the process.
    'state'code	int		{0, 10, 20,
    30, 40, 100,
    200, 1000}	State of the process.
    'statename'	str		'STOPPED'
    'STARTING'
    'RUNNING'
    'BACKOFF'
    'STOPPING'
    'EXITED'
    'FATAL'
    'UNKNOWN'	State of the process.
    'addresses'	list(str)			List of all addresses where the process is running.
    If more than one element in list, consider that a conflict is in progress.

get_all_process_info()
    Return information about all processes managed in Supvisors.
    @throws RPCError: with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION.
    @return list: a list of structures containing data about all processes.

get_process_rules(namespec)
    Return the rules used to deploy the process named namespec
    @param string namespec: the process name (or 'group:name', or 'group:\*')
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION,
        * with code Faults.BAD_NAME if namespec is unknown to Supvisors.

    @return list: a list of structures containing data about the deployment rules
    Key	Type	Unit	Validity	Description
    'application_name'	str			Name of the process' application.
    'process_name'	str			Name of the process.
    'addresses'	list(str)			List of all addresses where the process can be started.
    'start_sequence'	int		[0;127]	Starting order of the process when starting the related application.
    'stop_sequence'	int		[0;127]	Stopping order of the process when stopping the related application.
    'required'	bool			Importance of the process in the application.
    'wait_exit'	bool			True if Supvisors has to wait for the process to exit before triggering the next deployment phase.
    'loading'	int		[0;100]	Expected loading of the process when RUNNING.

get_conflicts()
    Return the conflicting processes
    @throws RPCError: with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION.
    @return list: a list of structures containing data about the conflicting processes
    Key	Type	Unit	Validity	Description
    'process_name'	str	Namespec of the process.
    'state'	str	State of the process.
    'address'	list(str)	List of all addresses where the process is running.
    If more than one element in list, consider that a conflict is in progress.


.. _xml_rpc_supvisors:

**Supvisors** Control
---------------------

restart()
    Restart Supvisors through all remote Supervisor instances
    @throws RPCError: with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION.
    @return boolean: always True unless error

shutdown()
    Shut down Supvisors through all remote Supervisor instances
    @throws RPCError: with code Faults.BAD_SUPVISORS_STATE if Supvisors is still in state INITIALIZATION.
    @return boolean: always True unless error


.. _xml_rpc_application:

Application Control
-------------------

start_application(strategy, application_name, wait=True)
    Start the processes related to the application named application_name in accordance with the strategy and the rules defined in the deployment file
    @param DeploymentStrategies strategy: the strategy to use for choosing an address
    @param string application_name: the name of the application
    @param boolean wait: wait for the application to be fully started
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is not in state OPERATION
        * with code Faults.BAD_STRATEGY if strategy is unknown to Supvisors
        * with code Faults.BAD_NAME if application_name is unknown to Supvisors
        * with code Faults.ALREADY_STARTED if application is RUNNING
        * with code Faults.ABNORMAL_TERMINATION if application could not be started

    @return boolean: always True unless error or nothing to start

stop_application(application_name, wait=True)
    Stop the running processes related to the application named application_name
    @param string application_name: the name of the application
    @param boolean wait: wait for the application to be fully stopped
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is not in state OPERATION or CONCILIATION
        * with code Faults.BAD_NAME if application_name is unknown to Supvisors

    @return boolean: always True unless error

restart_application(strategy, application_name, wait=True)
    Restart the processes related to the application named application_name in accordance with the strategy and the rules defined in the deployment file
    @param DeploymentStrategies strategy: the strategy to use for choosing an address
    @param string application_name: the name of the application
    @param boolean wait: wait for the application to be fully restarted
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is not in state OPERATION
        * with code Faults.BAD_STRATEGY if strategy is unknown to Supvisors
        * with code Faults.BAD_NAME if application_name is unknown to Supvisors
        * with code Faults.ALREADY_STARTED if application is RUNNING
        * with code Faults.ABNORMAL_TERMINATION if application could not be started

    @return boolean: always True unless error


.. _xml_rpc_process:

Process Control
---------------

start_args(namespec, extra_args=None, wait=True)
    Start a process upon request of the Deployer of Supvisors
    The behaviour is different from supervisor.startProcess as it sets the process state to FATAL instead of throwing an exception to the RPC client
    In addition to that, it is possible to pass extra arguments to the command line
    @param string namespec: the process name
    @param string extra_args: the additional arguments to be passed to the command line
    @param boolean wait: wait for the process to be fully started
    @throws RPCError:

        * with code Faults.BAD_NAME if namespec is unknown to the local Supervisor
        * with code Faults.BAD_EXTRA_ARGUMENTS if program is required or has a start sequence
        * with code Faults.ALREADY_STARTED if process is RUNNING
        * with code Faults.ABNORMAL_TERMINATION if process could not be started

    @return boolean: always True unless error

start_process(strategy, namespec, extra_args=None, wait=True)
    Start the process named namespec in accordance with the strategy and the rules defined in the deployment file
    Additional arguments can be passed to the command line using the extra_ags parameter.
    WARN: the 'wait_exit' rule is not considered here
    @param DeploymentStrategies strategy: the strategy to use for choosing an address
    @param string namespec: the process name (or 'group:name', or 'group:\*')
    @param string extra_args: the additional arguments to be passed to the command line
    @param boolean wait: wait for the process to be fully started
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is not in state OPERATION
        * with code Faults.BAD_STRATEGY if strategy is unknown to Supvisors
        * with code Faults.BAD_NAME if namespec is unknown to Supvisors
        * with code Faults.ALREADY_STARTED if process is RUNNING
        * with code Faults.ABNORMAL_TERMINATION if process could not be started

    @return boolean: always True unless error

stop_process(namespec, wait=True)
    Stop the process named namespec where it is running
    @param string namespec: the process name (or 'group:name', or 'group:\*')
    @param boolean wait: wait for the process to be fully stopped
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is not in state OPERATION or CONCILIATION
        * with code Faults.BAD_NAME if namespec is unknown to Supvisors

    @return boolean: always True unless error

restart_process(strategy, namespec, wait=True)
    Stop the process named namespec where it is running and restart it in accordance with the strategy and the rules defined in the deployment file
    WARN: the 'wait_exit' rule is not considered here
    @param DeploymentStrategies strategy: the strategy to use for choosing an address
    @param string namespec: the process name (or 'group:name', or 'group:\*')
    @param boolean wait: wait for the process to be fully restarted
    @throws RPCError:

        * with code Faults.BAD_SUPVISORS_STATE if Supvisors is not in state OPERATION
        * with code Faults.BAD_STRATEGY if strategy is unknown to Supvisors
        * with code Faults.BAD_NAME if namespec is unknown to Supvisors
        * with code Faults.ALREADY_STARTED if process is RUNNING
        * with code Faults.ABNORMAL_TERMINATION if process could not be started

    @return boolean: always True unless error


XML-RPC Clients
---------------

This section explains how to use the XML-RPC API from a Python, JAVA or C++ client.

Python Client
~~~~~~~~~~~~~

There are two possibilities to perform an XML-RPC from a python client.
For both methods, it is assumed that the env parameter contains the relevant HTTP configuration, as it would be set for a process spawed by Supervisor.
Both methods don't require any additional third party.

The first is to use the getRPCInterface of the supervisor.childutils module.
This is available in Supervisor but it works only for the local address.

.. code-block:: python

    import os
    from supervisor.childutils import getRPCInterface

    proxy = getRPCInterface(os.environ)
    proxy.supervisor.getState()
    proxy.supvisors.get_supvisors_state()

The second possibility is to use the getRPCInterface of the supvisors.rpcrequests module.
This is available in Supvisors and works for all addresses with a Supervisor daemon running with the same HTTP configuration as the local one.

.. code-block:: python

    import os
    from supvisors.rpcrequests import getRPCInterface

    proxy = getRPCInterface(address, os.environ)
    proxy.supervisor.getState()
    proxy.supvisors.get_supvisors_state()

JAVA Client
~~~~~~~~~~~

There is JAVA client supervisord4j referenced in the Supervisor documentation.
However, it comes with the following drawbacks, taken from the README.md of supervisord4j:

    * of course, it doesn't include the Supvisors XML-RPC API,
    * some XML-RPC are not implemented,
    * some implemented XML-RPC are not tested.

Supvisors provides a JAVA client in the client/java directory of the Supvisors installation directory.
This classes of the org.supvisors.rpc package implement all XML-RPC of all interfaces (system, supervisor and supvisors).
It requires the following additional dependency: Apache XML-RPC.
The binary JAR of Apache XML-RPC 3.1.3 is available in the MAVEN repository.

.. code-block:: java

    import org.supvisors.rpc.*;

    // create proxy
    SupervisorXmlRpcClient client = new SupervisorXmlRpcClient("10.0.0.1", 60000, "toto", "p@$$w0rd");

    // Supervisor XML-RPC
    SupervisorXmlRpc supervisor = new SupervisorXmlRpc(client);
    System.out.println(supervisor.getState());

    // Supvisors XML-RPC
    SupvisorsXmlRpc supvisors = new SupervisorXmlRpc(client);
    System.out.println(supvisors.getSupvisorsState());

C++ Client
~~~~~~~~~~

Not implemented yet

