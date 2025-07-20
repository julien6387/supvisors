.. _extended_supervisorctl:

:program:`supervisorctl` extension
==================================

This is an extension of the existing :program:`supervisorctl` API.
The additional commands provided by |Supvisors| are available by typing :command:`help` at the prompt.

.. important::

    When :program:`supervisorctl` is used with the option ``-s URL``, |Supervisor| does not provide access to the
    extended API. This is tracked through `Supervisor #1455 <https://github.com/Supervisor/supervisor/issues/1455>`_.

    |Supvisors| alleviates the problem by providing the command :program:`supvisorsctl` that works with all options.
    The use of :program:`supvisorsctl` is thus preferred to avoid issues, although :program:`supervisorctl` is suitable
    when used - explicitly or not - with a configuration file.

    In the same vein, the implementation of `Supervisor #591 <https://github.com/Supervisor/supervisor/issues/1455>`_
    has introduced a new ``RPCError`` exception code (``Faults.DISABLED``) that can be raised from |Supervisor|
    ``startProcess`` XML-RPC. Again, using :program:`supervisorctl` with the option ``-s URL`` will raise an unknown
    result code where :program:`supvisorsctl` will handle it properly.

.. code-block:: bash

    [bash] > supvisorsctl help

    default commands (type help <topic>):
    =====================================
    add    exit      open  reload  restart   start   tail
    avail  fg        pid   remove  shutdown  status  update
    clear  maintail  quit  reread  signal    stop    version


    supvisors commands (type help <topic>):
    =======================================
    all_start             local_status            start_application
    all_start_args        loglevel                start_args
    application_info      master                  start_process
    application_rules     process_rules           start_process_args
    conciliate            restart_application     stats_period
    conflicts             restart_process         stats_status
    disable               restart_sequence        stop_application
    disable_stats         sreload                 stop_process
    enable                sshutdown               strategies
    enable_stats          sstate                  sversion
    end_sync              sstatus                 test_start_application
    instance_status       start_any_process       test_start_process
    lazy_update_numprocs  start_any_process_args  update_numprocs

.. _extended_status:

Status
------

``sversion``

    Get the API version of |Supvisors|.

``sstate``

    Get the |Supvisors| global state and modes.

``sstate identifier``

    Get the |Supvisors| instance state and modes.

``master``

    Get the deduced name of the |Supvisors| *Master* instance.

``strategies``

    Get the strategies applied in |Supvisors|.

``instance_status``

    Get the status of all |Supvisors| instances.

``instance_status identifier``

    Get the status of the |Supvisors| instance identified by its deduced name.

``instance_status identifier1 identifier2``

    Get the status for multiple |Supervisor| instances identified by their deduced name.

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

    Get the local status (subset of |Supervisor| status, with extra arguments) of all processes.

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

    Get the |Supvisors| conflicts among the *managed* applications.


.. _supvisors_control:

|Supvisors| Control
-------------------

``loglevel level``

    Change the level of the |Supvisors| logger.

``conciliate strategy``

    Conciliate the conflicts detected by |Supvisors| if default strategy is ``USER`` and |Supvisors| is
    in ``CONCILIATION``` state.

``restart_sequence``

    Triggers the whole |Supvisors| start sequence.

``sreload``

    Restart all |Supvisors| instances.

``sshutdown``

    Shutdown all |Supvisors| instances.


.. _statistics_control:

Statistics Control
------------------

``stats_status``

    Get the |Supvisors| statistics collection status.

``enable_stats process``

    Enable process statistics collection

``enable_stats host process``

    Enable host and process statistics collection.

``disable_stats host``

    Disable host statistics collection.

``disable_stats all``

    Disable host and process statistics collection.

``stats_period period``

    Update the host and process statistics collection period.


.. _application_control:

Application Control
-------------------

From this part, a starting strategy may be required in the command lines.
It can take values among { ``CONFIG``, ``LESS_LOADED``, ``MOST_LOADED``, ``LOCAL``, ``LESS_LOADED_NODE``,
``MOST_LOADED_NODE`` }.

``start_application strategy``

    Start all managed applications with a starting strategy.

``start_application strategy appli``

    Start the managed application named appli with a starting strategy.

``start_application strategy appli1 appli2``

    Start multiple named managed applications with a starting strategy.

``stop_application``

    Stop all managed applications.

``stop_application appli``

    Stop the managed application named appli.

``stop_application appli1 appli2``

    Stop multiple named mnaged applications.

``restart_application strategy``

    Restart all managed applications with a starting strategy.

``restart_application strategy appli``

    Restart the managed application named appli with a starting strategy.

``restart_application strategy appli1 appli2``

    Restart multiple named managed applications with a starting strategy.

``test_start_application strategy appli``

    Return a prediction of the distribution of the managed application named appli with a starting strategy.



Process Control
---------------

``start_process strategy``

    Start all processes with a starting strategy.

``start_process strategy proc``

    Start the process named proc with a starting strategy.

``start_process strategy proc1 proc2``

    Start multiple named processes with a starting strategy.

``start_any_process strategy regex``

    Start a process whose namespec matches the regular expression and with a starting strategy.

``start_any_process strategy regex1 regex2``

    Start multiple processes whose namespec matches the regular expressions and with a starting strategy.

``start_args proc arg_list``

    Start the process named proc in the local |Supvisors| instance and with the additional arguments arg_list passed
    to the command line.

``start_process_args strategy proc arg_list``

    Start the process named proc with a starting strategy and with the additional arguments arg_list passed
    to the command line.

``start_any_process_args strategy regex arg_list``

    Start a process whose namespec matches the regular expression, using a starting strategy and additional arguments
    arg_list passed to the command line.

``all_start proc``

    Start the process named proc on all RUNNING |Supvisors| instances.

``all_start_args proc arg_list``

    Start the process named proc on all RUNNING |Supvisors| instances and with the additional arguments arg_list passed
    to the command line.

``stop_process``

    Stop all processes on all addresses.

``stop_process proc``

    Stop the process named proc.

``stop_process proc1 proc2``

    Stop multiple named processes.

``restart_process strategy``

    Restart all processes with a starting strategy.

``restart_process strategy proc``

    Restart the process named proc with a starting strategy.

``restart_process strategy proc1 proc2``

    Restart multiple named process with a starting strategy.

``test_start_process strategy proc``

    Return a prediction of the distribution of the process named proc with a starting strategy.

``test_start_process strategy appli:*``

    Return a prediction of the distribution of all appli application processes with a starting strategy.

``update_numprocs program_name numprocs``

    Increase or decrease dynamically the program numprocs (including FastCGI programs and Event listeners),
    stopping the obsolete programs immediately.

``lazy_update_numprocs program_name numprocs``

    Increase or decrease dynamically the program numprocs (including FastCGI programs and Event listeners),
    giving a chance to the obsolete programs to end by themselves.

``enable program_name``

    Enable the processes corresponding to the program.

``disable program_name``

    Stop and disable the processes corresponding to the program.

.. include:: common.rst
