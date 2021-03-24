How to create a new plugin
==========================

Create a new plugin to connect Metagov to one or more external platforms or governance tools.

The plugin can implement one or several of the following capabilities:

1. Perform actions
2. Perform asynchronous governance processes

Create and register a plugin
**************************

Create a new file at ``metagov/plugins/exampl-plugin/models.py``. Begin by creating a proxy subclass of the ``Plugin`` Django model for our new plugin, ``ExamplePlugin``. This model goes in the ``models.py``.

Decorate the class with the ``@Registry.plugin`` decorator so that Metagov core picks it up.

If the plugin requires any configuration, such as an API key or server URL, define a ``jsonschema`` for the config shape. Metagov core will validate the configuration that is provided to the ``/community`` endpoint.

.. code-block:: python

    import metagov.core.plugin_decorators as Registry
    from metagov.core.models import Plugin

    @Registry.plugin
    class ExamplePlugin(Plugin):
        name = 'example-plugin'
        config_schema = {
            "type": "object",
            "properties": {
                "my_required_config": {"type": "string"},
                "my_optional_config": {"type": "integer"},
                "my_optional_config_2": {"type": "integer", "default": 100},
            },
            "required": ["my_required_config"]
        }

        class Meta:
            proxy = True
    

Add an action
*************

Add a function to your class and decorate it with the ``@Registry.action`` decorator.

In this example, the action will be exposed as an endpoint at ``/action/example-plugin.my-action``.

If the action fails, the function should raise an exception.

..
   _TODO define error type and structure

.. code-block:: python

        @Registry.action(
            slug='my-action',
            description='Perform an action on behalf of a user',
            input_schema=my_input_schema,
            output_schema=my_output_schema
        )
        def do_something(self, parameters, initiator):
            print(self.parameters) # parameters have been validated against `my_input_schema`
            print(self.config['my_required_config']) # access the plugin configuration, if needed
            return {'id': 123} # output will be validated against `my_output_schema`

Add a governance process
************************

Creating a proxy subclass of the ``GovernanceProcess`` Django model for our new governance process, ``MyGovProcess``. This model should be declared after the ``ExamplePlugin`` model.

Decorate it with the ``@Registry.governance_process`` decorator so that Metagov core picks it up.

In this example, the process will be exposed as an endpoint at ``/process/example-plugin.my-gov-process``.

See the :ref:`Autodocumentation <autodocs-ref>` and complete example plugin for more information on how to implement each function.

.. code-block:: python

    @Registry.governance_process
    class MyGovProcess(GovernanceProcess):
        name = 'my-gov-process'
        plugin_name = 'example-plugin'
        input_schema = {} #optional jsonschema for validation

        class Meta:
            proxy = True

        def start(self, parameters):
            # kick off the asynchronous governance process and return immediately
            pass

        def close(self):
            # close the governance process; save the outcome
            pass

        def poll(self):
            # poll the governance process; update state if necessary
            pass

        def receive_webhook(self):
            # receive incoming webhook; update state if necessary
            pass
