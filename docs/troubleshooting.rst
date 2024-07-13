.. _troubleshooting:

Troubleshooting
===============

This section deals with frequent problems that could happen when experiencing |Supvisors| for the first time.

It is assumed that |Supervisor| is operational without the |Supvisors| plugin.

|Supvisors| plugin cannot be resolved
-------------------------------------

.. code-block:: bash

    [bash] > supervisord -n
    Error: supvisors.plugin:make_supvisors_rpcinterface cannot be resolved within [rpcinterface:supvisors]
    For help, use /usr/local/bin/supervisord -h

This error happens in a early stage of |Supervisor| startup, when the plugin factory is called.

Just in case, make sure that ``supvisors.plugin:make_supvisors_rpcinterface`` has been copied correctly.
Otherwise, this is the symptom of an improper |Supvisors| installation.

.. important::

    |Supvisors| requires a :program:`Python` version greater than 3.6 and must be available from the :program:`Python`
    interpreter used by |Supervisor|'s :command:`supervisord` command.

Upon any doubt, check the :program:`Python` version and start the interpreter in a terminal to test the import
of |Supvisors|:

.. code-block:: bash

    [bash] > which supervisord
    /usr/local/bin/supervisord

    [bash] > head -1 /usr/local/bin/supervisord
    #!/usr/bin/python

    [bash] > /usr/bin/python --version
    Python 3.9.6

    [bash] > /usr/bin/python
    Python 3.9.6 (default, Nov  9 2021, 13:31:27)
    [GCC 8.5.0 20210514 (Red Hat 8.5.0-3)] on linux
    Type "help", "copyright", "credits" or "license" for more information.
    >>> import supvisors
    >>>

If an ``ImportError`` is raised, here follow some possible causes:

Wrong pip program
~~~~~~~~~~~~~~~~~

*Issue:* |Supvisors| may have been installed with a :command:`pip` command corresponding to another :program:`Python`
version.

*Solution:* Install |Supvisors| using the :command:`pip` command whose version corresponds to the :program:`Python`
version used by |Supervisor|.

.. code-block:: bash

    [bash] > /usr/bin/python --version
    Python 3.9.6

    [bash] > /usr/bin/pip --version
    pip 20.2.4 from /usr/lib/python3.9/site-packages/pip (python 3.9)


Local |Supvisors| not in ``PYTHONPATH``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* In the case where |Supvisors| is not installed in the :program:`Python` packages, but used from a local
directory, the ``PYTHONPATH`` environment variable may not include the |Supvisors| location.

*Solution:* Set the |Supvisors| location in the ``PYTHONPATH`` environment variable before starting |Supervisor|.

.. code-block:: bash

    [bash] > ls -d ~/python/supvisors/supvisors/__init__.py
    /home/user/python/my_packages/supvisors/__init__.py
    [bash] > export PYTHONPATH=/home/user/python/my_packages:$PYTHONPATH
    [bash] > supervisord


Incorrect UNIX permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* The user cannot read the |Supvisors| files installed (via :command:`pip` or pointed by ``PYTHONPATH``).

*Solution*: Update the UNIX permissions of the |Supvisors| package so that its files can be read by any user.

.. code-block:: bash

    [user bash] > ls -l /usr/local/lib/python3.9/site-packages/supvisors/__init__.py
    -rw-------. 1 root root 56 Feb 28  2022 /usr/local/lib/python3.9/site-packages/supvisors/__init__.py
    [user bash] > su -
    Password:
    [root bash] > chmod -R a+r /usr/local/lib/python3.9/site-packages/supvisors
    [root bash] > exit
    exit
    [user bash] > ls -l /usr/local/lib/python3.9/site-packages/supvisors/__init__.py
    -rw-r--r--. 1 root root 56 Feb 28  2022 /usr/local/lib/python3.9/site-packages/supvisors/__init__.py
    [bash] > supervisord


Could not make supvisors rpc interface
--------------------------------------

At this stage, there must be some log traces available.
If the startup of |Supervisor| ends with the following lines, there must be an issue with the |Supvisors| configuration,
and more particularly with the option ``supvisors_list``.

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-17 17:47:15,101 INFO RPC interface 'supervisor' initialized
    [...]
    Error: Could not make supvisors rpc interface
    For help, use /usr/local/bin/supervisord -h

There are 4 main causes to that.

No inet_http_server
~~~~~~~~~~~~~~~~~~~

*Issue:* |Supervisor| is configured without any ``inet_http_server``.

*Solution:*  Configure |Supervisor| with a ``inet_http_server``.

The aim of |Supvisors| is to deal with applications distributed over several hosts so it cannot work with a |Supervisor|
configured with an ``unix_http_server``.

Based on the the following |Supvisors| configuration including only an ``unix_http_server``:

.. code-block:: ini

    [unix_http_server]
    file=/tmp/supervisor.sock

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface

If |Supervisor| is started from the local host, the following log traces will be displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 15:21:20,166 INFO RPC interface 'supervisor' initialized
    2022-11-18 15:21:20,184;WARN;Traceback (most recent call last):
      File "/usr/local/lib/python3.9/site-packages/supervisor-4.2.4-py3.9.egg/supervisor/http.py", line 821, in make_http_servers
        inst = factory(supervisord, **d)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/plugin.py", line 128, in make_supvisors_rpcinterface
        supervisord.supvisors = Supvisors(supervisord, **config)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/initializer.py", line 94, in __init__
        self.supervisor_data = SupervisorData(self, supervisor)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/supervisordata.py", line 94, in __init__
        raise ValueError(f'Supervisor MUST be configured using inet_http_server: {supervisord.options.configfile}')
    ValueError: Supervisor MUST be configured using inet_http_server: etc/supervisord.conf

    Error: Could not make supvisors rpc interface
    For help, use /usr/local/bin/supervisord -h


Incorrect Host name or IP address
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* The option ``supvisors_list`` includes a host name or an IP address that is unknown to the network
configuration of the local host.

*Solution:* Either fix the host name / IP address, or update your network configuration or remove the entry.

Based on the the following |Supvisors| configuration including an unknown host name:

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = unknown_host,rocky51,rocky52

If |Supervisor| is started from the hosts ``rocky51`` or ``rocky52``, the following log traces will be displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-17 17:47:15,120;ERRO;get_node_names: unknown host unknown_host
    2022-11-17 18:43:52,834;CRIT;Wrong Supvisors configuration (supvisors_list)
    2022-11-17 18:42:24,352;WARN;Traceback (most recent call last):
      File "/usr/local/lib/python3.9/site-packages/supervisor-4.2.4-py3.9.egg/supervisor/http.py", line 821, in make_http_servers
        inst = factory(supervisord, **d)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/plugin.py", line 128, in make_supvisors_rpcinterface
        supervisord.supvisors = Supvisors(supervisord, **config)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/initializer.py", line 98, in __init__
        self.supvisors_mapper.configure(self.options.supvisors_list, self.options.core_identifiers)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/supvisorsmapper.py", line 236, in configure
        raise ValueError(message)
    ValueError: could not define a Supvisors identification from "unknown_host"

    Error: Could not make supvisors rpc interface
    For help, use /usr/local/bin/supervisord -h

In the event where the host name or IP address seems legit to the user, here are a few explanations about how |Supvisors|
identifies the local |Supervisor| instance among the ``supvisors_list`` elements:

    - |Supvisors| extracts the ``host_name`` from the ``<identifier>host_name:http_port:internal_port`` element
      and stores the host name and aliases returned by the ``socket.gethostbyaddr`` function.
    - |Supvisors| considers that the local |Supervisor| instance is the element whose fully-qualified domain name,
      as returned by the ``socket.getfqdn`` function, belongs to the list of host name and aliases.

From the example below, the values ``rocky51.cliche.bzh``, ``rocky51`` and ``192.168.1.65`` are valid ``host_name``
elements to be used in ``supvisors_list``.

.. code-block:: python

    >>> from socket import gethostbyaddr, getfqdn
    >>> gethostbyaddr('rocky51.cliche.bzh')
    ('rocky51.cliche.bzh', ['rocky51'], ['192.168.1.65'])
    >>> gethostbyaddr('rocky51')
    ('rocky51.cliche.bzh', ['rocky51'], ['192.168.1.65'])
    >>> gethostbyaddr('192.168.1.65')
    ('rocky51.cliche.bzh', ['rocky51'], ['192.168.1.65'])
    >>> getfqdn()
    'rocky51.cliche.bzh'


Could not find local the local Supvisors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* The option ``supvisors_list`` does not include any host name or IP address corresponding to the local host.

*Solution:* Either add the local host to the list, or avoid to start |Supervisor| from the local host using this
configuration.

Based on the the following |Supvisors| configuration including 2 host names:

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = rocky52,rocky53

if |Supervisor| is started from a host that is not present in this list, the following traces will be displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-17 18:30:33,863;INFO;SupvisorsMapper.configure: identifiers=['rocky52', 'rocky53']
    2022-11-17 18:30:33,863;ERRO;SupvisorsMapper.find_local_identifier: could not find local the local Supvisors in supvisors_list
    2022-11-17 18:44:45,571;CRIT;Wrong Supvisors configuration (supvisors_list)
    2022-11-17 18:44:45,572;WARN;Traceback (most recent call last):
      File "/usr/local/lib/python3.9/site-packages/supervisor-4.2.4-py3.9.egg/supervisor/http.py", line 821, in make_http_servers
        inst = factory(supervisord, **d)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/plugin.py", line 128, in make_supvisors_rpcinterface
        supervisord.supvisors = Supvisors(supervisord, **config)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/initializer.py", line 98, in __init__
        self.supvisors_mapper.configure(self.options.supvisors_list, self.options.core_identifiers)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/supvisorsmapper.py", line 240, in configure
        self.find_local_identifier()
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/supvisorsmapper.py", line 269, in find_local_identifier
        raise ValueError(message)
    ValueError: could not find the local Supvisors in supvisors_list

    Error: Could not make supvisors rpc interface
    For help, use /usr/local/bin/supervisord -h


Multiple candidates for the local Supvisors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* This happens when multiple |Supvisors| instances have to be started on the same host. In that case, the option
``supvisors_list`` includes at least 2 host names or IP addresses referring to the same host and that have not been
qualified using a |Supervisor| identification.

*Solution:* Use the |Supervisor| identification option and apply it to the ``supvisors_list``.

Based on the the following |Supvisors| configuration including a host name ``rocky51`` and its IP address
``192.168.1.70``:

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = rocky51,rocky52,192.168.1.70:30000

if |Supervisor| is started from the host ``rocky51``, the following traces will be displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 10:42:25,931;INFO;SupvisorsMapper.configure: identifiers=['rocky51', 'rocky52', '192.168.1.70:30000']
    2022-11-18 10:42:25,931;ERRO;SupvisorsMapper.find_local_identifier: multiple candidates for the local Supvisors: ['rocky51', '192.168.1.70:30000']
    2022-11-18 10:42:25,931;CRIT;Wrong Supvisors configuration (supvisors_list)
    2022-11-18 10:42:25,940;WARN;Traceback (most recent call last):
      File "/usr/local/lib/python3.9/site-packages/supervisor-4.2.4-py3.9.egg/supervisor/http.py", line 821, in make_http_servers
        inst = factory(supervisord, **d)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/plugin.py", line 128, in make_supvisors_rpcinterface
        supervisord.supvisors = Supvisors(supervisord, **config)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/initializer.py", line 98, in __init__
        self.supvisors_mapper.configure(self.options.supvisors_list, self.options.core_identifiers)
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/supvisorsmapper.py", line 240, in configure
        self.find_local_identifier()
      File "/usr/local/lib/python3.9/site-packages/supvisors-0.15-py3.9.egg/supvisors/supvisorsmapper.py", line 269, in find_local_identifier
        raise ValueError(message)
    ValueError: multiple candidates for the local Supvisors: ['rocky51', '192.168.1.70:30000']

    Error: Could not make supvisors rpc interface
    For help, use /usr/local/bin/supervisord -h

At the moment, a solution in |Supvisors| is to qualify the entry in ``supvisors_list`` by adding its |Supervisor|
identifier. This is also the name that will be used for the Web UI.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = <supv-01>rocky51,rocky52,<supv-03>192.168.1.70:30000

Then |Supervisor| shall be started by passing this identification to the :program:`supervisord` program.

.. code-block:: bash

    [bash] > supervisord -ni supv-01


Remote host ``SILENT``
----------------------

A remote |Supvisors| instance may be declared ``SILENT``, although :program:`supervisord` is running on the remote host.

Firewall rules
~~~~~~~~~~~~~~

There is likely an issue with the firewall of the hosts. By default, a firewall is configured to block
almost everything. The |Supervisor| HTTP ports have to be explicitly allowed in the firewall configuration.

*Issue:* Without the |Supvisors| plugin, accessing the remote |Supervisor| web page using its URL is rejected.

*Solution:* Use HTTP ports that are allowed by the firewall or ask the UNIX administrator to enable the HTTP ports used
by the |Supervisor| configuration.


Inconsistent |Supvisors| configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* Accessing the remote |Supvisors| web page using its URL is accepted. Various error messages may be received.

*Solution:* Make sure that the ``supvisors_list`` is consistent for all |Supvisors| instances, in accordance with
:ref:`supvisors_section`.

When using a simple |Supervisor| / |Supvisors| configuration as follows:

.. code-block:: ini

    [inet_http_server]
    port=:60000

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = rocky51,rocky52,rocky53
    internal_port = 60001

It is assumed that :program:`supervisord` will be started on the 3 hosts with the same configuration, i.e. with a
|Supervisor| server available on port 60000 and with |Supvisors| internal publisher available on port 60001.

If the |Supervisor| configuration on rocky52 is different and declares an ``inet_http_server`` on port 60100,
the XML-RPC from rocky51 and rocky53 towards rocky52 will fail.

A variety of different errors may be experienced depending on how wrong configuration is.

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 18:16:20,428;ERRO;Context.on_tick_event: got tick from unknown Supvisors=rocky52
    [...]
    [ERROR] failed to check Supvisors=rocky52
    [...]


Discovery mode not working
--------------------------

When |Supvisors| is in discovery mode, it uses an UDP Multicast group to share the identification of every |Supvisors|
instance periodically. The relevant configuration options in the |Supervisor| configuration file are:

    * ``multicast_group``,
    * ``multicast_interface``,
    * ``multicast_ttl``.

When |Supvisors| is running with a multicast group set, the following command should show the multicast address chosen.
Based on a multicast address ``239.0.0.1`` and a multicast interface ``eth0``

.. code-block:: bash

    [bash] > netstat -g
    IPv6/IPv4 Group Memberships
    Interface       RefCnt Group
    --------------- ------ ---------------------
    [...]
    eth0            2      239.0.0.1
    [...]

There are quite a number of reasons that may cause this function to not work, at OS level and in the |Supvisors|
configuration.

The consequence is always the same: the remote |Supvisors| instance is not detected, although :program:`supervisord`
is running on the remote host.

The main difficulty is that there will be no log trace to help in |Supvisors|, due to the non-connected nature of UDP.
UDP sockets are open and eventually bound but nothing happens on them.

First of all, it is absolutely mandatory that multicast is enabled in the system nodes and the hardware in-between.

The aim of this section is clearly not to be a tutorial about configuring multicast in a system, which is not really
in my area of expertise anyway. The aim is to help the |Supvisors| user and/or his favorite system administrator,
by giving a few common hints.

A basic multicast exchange using a tool like :program:`iperf` can be done in order to discharge |Supvisors|.

``MULTICAST`` not activated on the network device
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* Multicast is not activated on the network device.

Here are 2 unix commands that provide feedback on the multicast status of the ``eth0`` network device.

.. code-block:: bash

    [bash] > ifconfig eth0
    eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
    [...]

    [bash] > ip addr show eth0
    2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    [...]

*Solution:* If ``MULTICAST`` is not displayed for the considered network interface, the following
command should do the trick.

.. code-block:: bash

    [bash] > ip link set multicast on dev eth0

``IGMP`` not enabled in the firewall
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* The ``IGMP`` protocol is not enabled in the firewall daemon (default configuration).

*Solution:* The following commands enable permanently ``IGMP`` for a zone:

.. code-block:: bash

    [bash] > firewall-cmd --permanent --zone=zone-name --add-protocol=igmp
    [bash] > firewall-cmd --reload

Multicast denied by an ACL
~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* Multicast is working between co-located |Supvisors| instances, but not with |Supvisors| instances located
on remote hosts, and separated only by a network switch.

*Solution:* Depending on the network configuration and hardware, multicast may also be denied by an ACL on a switch.
This is quite specific to the firmware involved, so refer to the switch documentation.

Multicast not enabled in a router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* Multicast is working between co-located |Supvisors| instances, but not with |Supvisors| instances located
on remote hosts, and separated by a router.

*Solution:* Multicast may be disabled in the router. Again, this is quite specific to the firmware involved, so refer
to the switch documentation.

As an example, multicast can be enabled in a *CISCO* router with the following command:

.. code-block:: bash

    ip multicast-routing

TTL too low
~~~~~~~~~~~

*Issue:* Same issue as above, despite multicast is enabled in the router.

The Time-To-Live (TTL) of a multicast message is decremented everytime it passes through a router, and in accordance
with the router threshold. When the TTL is lower than the router threshold, the message is discarded.

*Solution:* The TTL value in the ``multicast_ttl`` option should be set accordingly with the configuration
of the routers between any of the |Supvisors| instances. The router threshold could also be decreased.

Incompatible candidates
~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* Multicast is confirmed working (outside the scope of |Supvisors|) and the following log trace occurs:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2024-07-05 18:24:45,204;WARN;SupvisorsMapper.check_candidate: the Supvisors instance known as <test>rocky51:60000 is incompatible with the candidate <test>rocky52:60000
    [...]

This can happen in discovery mode when at least 2 |Supvisors| instances have the same nick identifier.
The nick identifier can be optionally set:

    * either in the |Supervisor| configuration file:

        .. code-block:: ini

            [supervisord]
            ...
            identifier=test

    * or when starting the :program:`supervisord` daemon:

        .. code-block:: bash

            [bash] > supervisord -ni test
            [...]

When this option is set, and thus different from the default value "supervisor", it MUST be unique per instance.

*Solution:* There are a few alternatives:

    * leave the ``identifier`` option unset and let |Supvisors| build a default ``nick_identifier`` ;
    * ensure that :program:`supervisord` is started using the ``-i`` option and with a different parameter
      for every |Supvisors| instance,
    * use a different |Supervisor| configuration file per |Supvisors| instance.


Empty Application menu
----------------------

The Application Menu in the |Supvisors| Web UI unexpectedly contains only the application template.

In the |Supvisors| Web UI, it may happen that the Application Menu (see :ref:`dashboard`) contains only the application
template. In this case, all applications are considered *Unmanaged*.

Wrong ``rules_files``
~~~~~~~~~~~~~~~~~~~~~

*Issue:* The ``rules_files`` option is not set or the targeted files are not reachable.

*Solution:* Make sure that the ``rules_files`` option is set with reachable files.

When the ``rules_files`` option is set and |Supvisors| does not find any corresponding file, the following log trace
is displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 19:22:53,201;WARN;SupvisorsOptions.to_filepaths: no rules file found
    [...]

XML file not readable
~~~~~~~~~~~~~~~~~~~~~

*Issue:* The user cannot read the |Supvisors| XML rules file.

*Solution*: Update the UNIX permissions of the |Supvisors| XML rules file so that it can be read by the user.

When the ``rules_files`` option is set with a file that cannot be read, the following log trace is displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 19:33:19,793;INFO;Parser: parsing rules from my_movies.xml
    2022-11-18 19:33:19,797;WARN;Supvisors: cannot parse rules files: ['my_movies.xml'] - Error reading file 'my_movies.xml': failed to load external entity "my_movies.xml"
    [...]

XML file invalid
~~~~~~~~~~~~~~~~

*Issue:* The |Supvisors| XML rules file is syntactically incorrect.

*Solution*: Fix the |Supvisors| XML rules file syntax.

When the ``rules_files`` option is set with a file that is syntactically incorrect, the following log trace
is displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 19:26:34,713;INFO;Parser: parsing rules from my_movies.xml
    2022-11-18 19:26:35,448;WARN;Supvisors: cannot parse rules files: ['my_movies.xml'] - expected '>', line 83, column 13 (my_movies.xml, line 83)
    [...]

.. hint::

    The XSD file :file:`rules.xsd` provided in the |Supvisors| package can be used to validate the XML rules files.

    .. code-block:: bash

        [bash] > xmllint --noout --schema rules.xsd my_movies.xml


No application declared
~~~~~~~~~~~~~~~~~~~~~~~

*Issue:* The |Supvisors| XML rules file has been parsed correctly but still no application in the menu of the Web UI.

*Solution*: For the |Supervisor| group name considered, make sure that an application element exists in a |Supvisors|
XML rules file.

So considering this group definition in |Supervisor| configuration:

.. code-block:: ini

    [group:my_movies]
    programs=program_1,program_2

An application element has to be included in a |Supvisors| XML rules file to make it *Managed* and displayed in the
Application menu of the |Supvisors| Web UI.

.. code-block:: xml

    <root>
        <application name="my_movies"/>
    </root>

.. include:: common.rst
