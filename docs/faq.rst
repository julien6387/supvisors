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

the following hint will provide a way to do it without updating |Supvisors|, based on a simple bootstrap
and monkeypatch.

Every Supvisors ``XHTML`` page include a style instruction that can be used to inject user ``CSS`` by code.
It is placed after the inclusion of all ``CSS`` files, so that the user ``CSS`` may overwrite anything.

.. code-block:: html

    <style meld:id="style_mid"> </style>

The bootstrap consists in inserting some user code between the |Supervisor| plugin factory and the |Supvisors| plugin
creation. The code will create the |Supvisors| plugin and monkeypatch the ``ViewHandler.write_style`` method,
so that the style instruction above is filled with ``CSS`` instructions that can be hardcoded as shown below
or simply read from a file.

.. code-block:: python

    from supvisors.plugin import make_supvisors_rpcinterface
    from supvisors.web.viewhandler import ViewHandler

    USER_CSS = """
    div {
        background-color: black;
    }
    """

    def write_style(self, root):
        """ Insert additional CSS instructions into the pages. """
        root.findmeld('style_mid').content(USER_CSS)

    def make_user_rpcinterface(supervisord, **config):
        """ Create the Supvisors plugin and monkeypatch the write_style method. """
        intf = make_supvisors_rpcinterface(supervisord, **config)
        ViewHandler.write_style = write_style
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
