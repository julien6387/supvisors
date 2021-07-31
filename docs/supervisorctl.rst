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
    =======================================
    address_status     loglevel             sshutdown          start_process_args
    application_info   master               sstate             stop_application
    application_rules  process_rules        sstatus            stop_process
    conciliate         restart_application  start_application  strategies
    conflicts          restart_process      start_args         sversion
    local_status       sreload              start_process


Status
------

``sversion``

    Get the API version of **Supvisors**.

``sstate``

    Get the **Supvisors** state.

``master``

    Get the **Supvisors** master address.

``strategies``

    Get the strategies applied in **Supvisors**.

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

``local_status``

    Get the local status (subset of Supervisor status, with extra arguments) of all processes.

``local_status proc``

    Get the local status of the process named proc.

``local_status appli:*``

    Get the local status of all processes in the application named appli.

``local_status proc1 proc2``

    Get the local status for multiple named processes.

``application_rules``

    Get the rules of all processes.

``application_rules appli``

    Get the rules of the applications named appli.

``application_rules appli1 appli2``

    Get the rules for multiple named applications.

``application_rules``

    Get the rules of all applications.

``process_rules proc``

    Get the rules of the process named proc.

``process_rules appli:*``

    Get the rules of all processes in the application named appli.

``process_rules proc1 proc2``

    Get the rules for multiple named processes.

``conflicts``

    Get the **Supvisors** conflicts among the *managed* applications.


**Supvisors** Control
---------------------

``loglevel level``

    Change the level of **Supvisors** logger.

``conciliate strategy``

    Conciliate the conflicts detected by **Supvisors** if default strategy is ``USER`` and **Supvisors** is in ``CONCILIATION``` state.

``sreload``

    Restart **Supvisors** through all Supervisor instances.

``sshutdown``

    Shutdown **Supvisors** through all Supervisor instances.


Application Control
-------------------

From this part, a starting strategy may be required in the command lines.
It can take values among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL`` }.

``start_application strategy``

    Start all applications with a starting strategy.

``start_application strategy appli``

    Start the application named appli with a starting strategy.

``start_application strategy appli1 appli2``

    Start multiple named applications with a starting strategy.

``stop_application``

    Stop all applications.

``stop_application appli``

    Stop the application named appli.

``stop_application appli1 appli2``

    Stop multiple named applications.

``restart_application strategy``

    Restart all applications with a starting strategy.

``restart_application strategy appli``

    Restart the application named appli with a starting strategy.

``restart_application strategy appli1 appli2``

    Restart multiple named applications with a starting strategy.


Process Control
---------------

``start_process strategy``

    Start all processes with a starting strategy.

``start_process strategy proc``

    Start the process named proc with a starting strategy.

``start_process strategy proc1 proc2``

    Start multiple named processes with a starting strategy.

``start_args proc arg_list``

    Start the process named proc on the local node and with the additional arguments arg_list passed to the command line.

``start_process_args strategy proc arg_list``

    Start the process named proc with a starting strategy and with the additional arguments arg_list passed to the command line.

``stop_process``

    Stop all processes on all addresses.

``stop_process proc``

    Stop the process named appli.

``stop_process proc1 proc2``

    Stop multiple named processes.

``restart_process strategy``

    Restart all processes with a starting strategy.

``restart_process strategy appli``

    Restart the process named appli with a starting strategy.

``restart_process strategy appli1 appli2``

    Restart multiple named process with a starting strategy.
