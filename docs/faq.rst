.. _faq:

Frequent Asked Questions
========================

How to change the Supvisors Web UI ?
------------------------------------

If the user is considering structural updates of the |Supvisors| Web UI, such as:

    * adding/removing information,
    * changing the ``XHTML`` elements structure,
    * adding ``Javascript`` code,

the recommended way to proceed is obviously to work on a fork and update the ``XHTML``, ``CSS`` and ``Python`` code
as needed.

However, if the updates under consideration are involving ``CSS`` only, such as:

    * updating resources (colors, fonts, font sizes, bitmaps),
    * updating object feedbacks (hover, active, focus),
    * reorganizing HTML elements (``div`` sizes and positions),
    * hiding some existing parts,

an option ``css_files`` has been added to the :ref:`supvisors_section` of the |Supervisor| configuration file.

.. code-block:: ini

    [rpcinterface:supvisors]
    supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    css_files = user.css

Every Supvisors ``XHTML`` page include a style instruction that can be used to inject user ``CSS``.
It is placed after the inclusion of all ``CSS`` files, so that the user ``CSS`` may overwrite anything.

.. code-block:: html

    <style meld:id="style_mid"> </style>

When the option is set, |Supvisors| concatenates all user CSS files and inserts the content in the HTML file.


Monkeypatching |Supvisors|
--------------------------

As Python is an interpreted language, and provided that the user has a good understanding of |Supvisors| and
|Supervisor|, the following bootstrap makes it possible to add / update fonctions to |Supvisors| on-the-fly.

|Supvisors| itself relies on monkeypatching |Supervisor| in a few places.

.. attention::

    This is obviously **at your own risk**!

.. code-block:: python

    from supvisors.plugin import make_supvisors_rpcinterface

    def make_user_rpcinterface(supervisord, **config):
        """ Create the Supvisors plugin and monkeypatch. """
        intf = make_supvisors_rpcinterface(supervisord, **config)
        # INSERT USER CODE
        # ...
        return inf


Finally, in the |Supervisor| configuration file, the |Supvisors| plugin has to be configured using the bootstrap
instead of the |Supvisors| usual function.

.. code-block:: ini

    [rpcinterface:supvisors]
    ;supervisor.rpcinterface_factory = supvisors.plugin:make_supvisors_rpcinterface
    supervisor.rpcinterface_factory = <user_python_module>:make_user_rpcinterface


.. important::

    Before starting the |Supervisor| daemon, ensure that the bootstrap is visible in the :command:`Python` context.
    It can be part of an installed :command:`Python` package or just set in the ``PYTHONPATH`` environment variable.

    .. code-block:: bash

        [bash] > export PYTHONPATH=<user_python_module_directory>:${PYTHONPATH}
        [bash] > supervisord


.. include:: common.rst
