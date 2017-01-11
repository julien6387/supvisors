:command:`supervisorctl` extension
==================================

This is an extension of the existing :command:`supervisorctl` API.
The additional commands provided by **Supvisors** are available by typing :command:`help` at the prompt.

.. code-block:: bash

    [bash] > supervisorctl help

    default commands (type help <topic>):
    =====================================
    add    exit      open  reload  restart   start   tail   
    avail  fg        pid   remove  shutdown  status  update 
    clear  maintail  quit  reread  signal    stop    version


    supvisors commands (type help <topic>):
    =========================================
    address_status       restart_process  sstatus             stop_application
    application_info     rules            start_application   stop_process    
    conflicts            sreload          start_args          sversion        
    master               sshutdown        start_process     
    restart_application  sstate           start_process_args

Status
------

``sversion``

    Get the API version of **Supvisors**.

``master``

    Get the **Supvisors** master address.

``sstate``

    Get the **Supvisors** state.

``address_status``

    Get the status of all Supervisor instances managed in **Supvisors**.

``address_status addr``

    Get the status of the Supervisor instance managed in **Supvisors** and running on addr.

``address_status addr1 addr2``

    Get the status for multiple addresses.

``application_info``

    Get the status of all applications.

``application_info appli``

    Get the status of application named appli.

``application_info appli1 appli2``

    Get the status for multiple named applications.

``sstatus``

    Get the status of all processes.

``sstatus proc``

    Get the status of the process named proc.

``sstatus appli:*``

    Get the status of all processes in the application named appli.

``sstatus proc1 proc2``

    Get the status for multiple named processes.

``rules``

    Get the deployment rules of all processes.

``rules proc``

    Get the deployment rules of the process named proc.

``rules appli:*``

    Get the deployment rules of all processes in the application named appli.

``rules proc1 proc2``

    Get the deployment rules for multiple named processes.

``conflicts``

    Get the **Supvisors** conflicts.


**Supvisors** Control
---------------------

``sreload``

    Restart **Supvisors** through all Supervisor instances.

``sshutdown``

    Shutdown **Supvisors** through all Supervisor instances.


Application Control
-------------------

``start_application strategy``

    Start all applications with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``start_application strategy appli``

    Start the application named appli with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``start_application strategy appli1 appli2``

    Start multiple named applications with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``stop_application``

    Stop all applications.

``stop_application appli``

    Stop the application named appli.

``stop_application appli1 appli2``

    Stop multiple named applications.

``restart_application strategy``

    Restart all applications with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``restart_application strategy appli``

    Restart the application named appli with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``restart_application strategy appli1 appli2``

    Restart multiple named applications with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.


Process Control
---------------

``start_process strategy``

    Start all processes with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``start_process strategy proc``

    Start the process named proc with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``start_process strategy proc1 proc2``

    Start multiple named processes with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``start_args proc arg_list``

    Start the process named proc on the local address and with the additional arguments arg_list passed to the command line.

``start_process_args strategy proc arg_list``

    Start the process named proc with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` } and with the additional arguments arg_list passed to the command line.

``stop_process``

    Stop all processes on all addresses.

``stop_process proc``

    Stop the process named appli.

``stop_process proc1 proc2``

    Stop multiple named processes.

``restart_process strategy``

    Restart all processes with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``restart_process strategy appli``

    Restart the process named appli with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.

``restart_process strategy appli1 appli2``

    Restart multiple named process with a strategy among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED`` }.


