.. _faq:

Frequent Asked Questions
========================

This section deals with frequent problems that could happen when experiencing |Supvisors| for the first time.

It is assumed that |Supervisor| is operational without the |Supvisors| plugin.

Cannot be resolved
------------------

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

*Issue:* In the case where |Supvisors| is not installed in the :program:`Python` packages but used from a local
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

*Solution*: Update the UNIX permissions of the |Supvisors| package so that its files can be read by the user.

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

In the event where the host name or IP address seems legit to the user, it has to be noted that |Supvisors| accepts only
the host name, aliases and IP addresses as returned by the ``gethostbyaddr`` function.

.. code-block:: python

    >>> from socket import gethostbyaddr
    >>> gethostbyaddr('rocky52')
    ('rocky52', [], ['192.168.1.65'])
    >>>


Local Supvisors not found
~~~~~~~~~~~~~~~~~~~~~~~~~

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


Multiple candidates
~~~~~~~~~~~~~~~~~~~

*Issue:* This happens when multiple |Supvisors| instances have to be started on the same host. In that case, the option
``supvisors_list`` includes at least 2 host names or IP addresses referring to the same host and that have not been
qualified using a |Supervisor| identification.

*Solution:* Use the |Supervisor| identification option and apply it to the ``supvisors_list``.

Based on the the following |Supvisors| configuration including a host name ``rocky51`` and its IP address
``192.168.1.70``:

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supvisors_list = rocky51,rocky52,192.168.1.70:30000:

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
    supvisors_list = <supv-01>rocky51,rocky52,<supv-03>192.168.1.70:30000:

Then |Supervisor| shall be started by passing this identification to the :program:`supervisord` program.

.. code-block:: bash

    [bash] > supervisord -ni supv-01


TCP port already bound
~~~~~~~~~~~~~~~~~~~~~~

*Issue:* The |Supvisors| state is stuck to the ``INITIALIZATION`` state on a host.

*Solution:* Check that the ``internal_port`` set in the |Supvisors| communication is not already used. If confirmed,
free the port or update the |Supvisors| configuration with an unused port.

|Supvisors| uses TCP to exchange data between |Supvisors| instances.
If the TCP communication fails on the host internal link, this is very likely because the TCP server could not bind on
the port specified. In such a case, the following log trace should be displayed:

.. code-block:: bash

    [bash] > supervisord -n
    [...]
    2022-11-18 12:21:49,026;CRIT;PublisherServer._bind: failed to bind the Supvisors publisher on port 60000
    [...]


Remote host ``SILENT``
----------------------

A remote |Supvisors| instance may be declared ``SILENT``, although :program:`supervisord` is running on the remote host.

The first thing to check is the |Supvisors| state on the remote host.

If the remote |Supvisors| instance is stuck in the ``INITIALIZATION`` state, it is very likely due to the problem
described just above in `TCP port already bound`_.

However, if the remote |Supvisors| instance is in the ``OPERATIONAL`` state, then there are 2 main causes.


Firewall configuration
~~~~~~~~~~~~~~~~~~~~~~

The first cause is a very frequent problem: the firewall of the hosts. By default, a firewall is configured to block
almost everything. TCP ports have to be explicitly allowed in the firewall configuration.

*Issue:* Without the |Supvisors| plugin, accessing the remote |Supervisor| web page using its URL is rejected.
For the sake of completeness, a test using the |Supvisors| ``internal_port`` as |Supervisor| INET HTTP port should be
done as well.

*Solution:* Use TCP ports that are allowed by the firewall or ask the UNIX administrator to enable the TCP ports used
by the |Supervisor| / |Supvisors| configuration.


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
