Special Functionalities
=======================

.. _start_sequence:

Start Sequence
--------------

When applying the ``CONFIG`` strategy, **Supvisors** chooses the first address available in the ``address_list``.

When applying the ``LESS_LOADED`` strategy, **Supvisors** chooses the address in the ``address_list``
having the lowest expected loading.
The aim is to distribute the process loading among the available hosts.

When applying the ``MOST_LOADED`` strategy, with respect of the common rules, **Supvisors** chooses the address
in the ``address_list`` having the greatest expected loading.
The aim is to maximize the load of a host before starting to load another host.
This strategy is more interesting when the resources are limited.


Stop Sequence
-------------

TODO


.. _auto_fencing:

Auto-Fencing
------------

Auto-fencing is applied when one of the **Supvisors** instance is seen as inactive (crash, system power down,
network failure) from the other **Supvisors** instances.
In this case, the running **Supvisors** instances disconnect the corresponding address from their subscription socket.
The address is marked as ``ISOLATED`` and, in accordance with the rules defined and the value of the ``autorestart``
option of the program, **Supvisors** may try to restart somewhere else the processes that were previously running
on that address.

In the case of a network failure, the same mechanism is of course applied on the other side. Here comes the premices
of a split-brain syndrome.

If the incriminated system restarts, or network failure is fixed, it receives

.. attention::
        
    **Supvisors** does NOT isolate the address at the operating system level, so that when the incriminated system
    becomes active again, it is still possible to perform network requests between all systems, despite the
    **Supvisors** instances do not communicate anymore.


.. _conciliation:

Conciliation
------------

When applying the ``SENICIDE`` strategy, **Supvisors** keeps the youngest process, i.e. the process that has been started the most recently, and stops all the others.

When applying the ``INFANTICIDE`` strategy, **Supvisors** keeps the oldest process and stops all the others.

When applying the ``USER`` strategy, **Supvisors** just waits that a user aplication solves the conflicts using :command:`supervisorctl`, XML-RPC, process signals, or any other solution.

When applying the ``STOP`` strategy, **Supvisors** stops all conflicting processes, which may lead the corresponding applications to a degraded state.

When applying the ``RESTART`` strategy, **Supvisors** stops all conflicting processes and restarts a new one.



Extra Arguments
---------------

TODO

