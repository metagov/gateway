Plugin Tutorial
===============
.. _plugintutorial-ref:
This tutorial will show you have to write a Metagov Plugin. It will demonstrate how to:

1. Create :ref:`Actions` (example: send a tweet)
2. Create a webhook :ref:`Listener` (example: handle events occurring on Open Collective)
3. Create asynchronous :ref:`Governance Processes` (example: perform a vote on Loomio)

This tutorial assumes that you have the Metagov Django service set up for local development.


Creating a Plugin
*****************

Start by creating a new folder with a couple files in it:

.. code-block:: shell

    metagov/plugins/tutorial/
        __init__.py             # required, but can be empty
        models.py               # filename is important

Next, we need to create a `Django proxy <https://docs.djangoproject.com/en/3.1/topics/db/models/#proxy-models>`_ subclass of the ``Plugin`` model.
This new model goes in the ``models.py`` file. Decorate the class with the ``@Registry.plugin`` decorator so that Metagov core picks it up.

.. code-block:: python

    import metagov.core.plugin_decorators as Registry
    from metagov.core.models import Plugin

    @Registry.plugin
    class Tutorial(Plugin):
        name = 'tutorial' # this is a unique slug for the plugin

        class Meta:
            proxy = True # required


Configuration
*************

If the plugin requires any configuration, such as an API key, you can define the configuration
properties as a ``jsonschema`` object. The configuration values will always be Community-specific.

.. code-block:: python

    @Registry.plugin
    class Tutorial(Plugin):
        name = 'tutorial'
        config_schema = {
            "type": "object",
            "properties": {
                "api_key": {"type": "string"},
                "foo": {"type": "string", "default": "bar"},
                "webhook_slug": {"type": "string"}
            },
            "required": ["api_key", "foo"]
        }

        class Meta:
            proxy = True

        def initialize(self):
            print(self.config)             # access the current config
            print(self.config["api_key"])  # safely access required properties, it has been validated

Special configuration properties:

* ``webhook_slug``: If you are implementing a webhook listener, you can include this special property. When set, metagov core will expose the webhook endpoint at this slug. This is useful for creating hard-to-guess webhook receiver URL, in cases where the incoming requests can not be validated.


Plugin Lifecycle
****************

Each plugin is a Django model. A new model instance is created each time the plugin is enabled for a given community.

The plugin instance is created when the plugin is enabled for a community, and it is destroyed when the plugin is disabled for that community.
If the community changes the plugin config, the plugin instance gets destroyed and recreated.

Initialize
^^^^^^^^^^

Override the ``initialize`` function to set up the plugin. It is called exactly once, when the plugin is created.


Persisting data
^^^^^^^^^^^^^^^

There may be times when you want to persist community-related data, so that it can be accessed by all actions, processes, and listeners.
This is possible by using the ``state`` attribute on the Plugin.
The data stored in ``state`` must be serializable using `jsonpickle <https://jsonpickle.github.io/>`_.

.. code-block:: python

    @Registry.plugin
    class Tutorial(Plugin):
        #..elided..

        def initialize(self):
            # ✅ set initial state
            self.state.set("foo", "bar")

            # 🛑 this won't be persisted
            self.foo = "bar"

        def my_action(self):
            value = self.state.get("foo")     # access state
            self.state.set("obj", {"x": 2})   # update state

.. note:: If the plugin config is changed, the plugin instance gets destroyed and recreated. At that point, all ``state`` is lost.

Enabling the Plugin for a Community
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To create a new community with your plugin activated, make a PUT request to the ``community`` endpoint:

.. code-block:: shell

    curl -X PUT 'http://127.0.0.1:8000/api/internal/community/my-community-1234' \
        -H 'Content-Type: application/json' \
        --data-raw '{
            "name": "my-community-1234",
            "readable_name": "",
            "plugins": [
                {
                    "name": "tutorial",
                    "config": {
                        "api_key": "ABC123",
                        "foo": "baz"
                    }
                }
            ]
        }'


See the Design Overview for more information about the data model.

Disabling the Plugin for a Community
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Disable the plugin by removing it from the community ``plugins`` list. When the plugin is disabled,
the Plugin model instance is deleted, and all data in ``state`` is lost.

.. code-block:: shell

    curl -X PUT 'http://127.0.0.1:8000/api/internal/community/my-community-1234' \
        -H 'Content-Type: application/json' \
        --data-raw '{
            "name": "my-community-1234",
            "readable_name": "",
            "plugins": []
        }'


Actions
*******

If you want to expose a way for the governance driver to **perform an action** or **get data**,
then you can implement an action. An action is just a function on your Plugin class that is registered
with metagov core, and exposed as an API endpoint at ``/api/internal/action/<plugin>.<slug>``.

All you need to do is decorate your function with the ``@Registry.action`` decorator:

..
   _TODO define error type and structure

.. code-block:: python

    @Registry.plugin
    class Tutorial(Plugin):
        #..elided..

        @Registry.action(
            slug='times-two',
            description='description for OpenAPI docs',
            input_schema=my_input_schema,     # optional jsonschema for parameters
            output_schema=my_output_schema    # optional jsonschema for return value
        )
        def times_two(self, parameters):
            num = parameters["value"]     # parameters have been validated against `my_input_schema`
            print(self.config["foo"])     # access the plugin configuration or plugin state, if needed
            return {"result": num * 2 }   # output will be validated against `my_output_schema`


Now you should be able to invoke the action through the Metagov API:

.. code-block:: shell

    curl -X POST 'http://127.0.0.1:8000/api/internal/action/tutorial.times-two' \
        -H 'Content-Type: application/json' \
        -H 'X-Metagov-Community: my-community-1234' \
        --data-raw '{
            "parameters": { "value": 5 }
        }'


Listener
********

If you want to listen to events occurring on another platform, and forward them to the governance driver so that
it can react to them, then you want to implement a **listener** in your plugin.

In order to do this, override the ``receive_webhook`` function to handle incoming webhook requests from the external platform.
Use the ``send_event_to_driver`` function to send the event to the Driver.
(See :ref:`Autodocumentation <autodocs-ref>` for more).

.. code-block:: python

    @Registry.plugin
    class Tutorial(Plugin):
        #..elided..

        def receive_webhook(self, request):
            body = json.loads(request.body)   # Django HttpRequest object
            print(body)
            data = body["data"]
            initiator = { "user_id": body["account"], "provider": "idenetity-provider-key" }
            # send the event to the driver
            self.send_event_to_driver(event_type="post_created", data=data, initiator=initiator)


Register the webhook receiver
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Metagov exposes a public webhook received endpoint for each active plugin instance.
For the plugin and community we created in this tutorial, the webhook receiver endpoint is either at:
``http://127.0.0.1:8000/api/hooks/my-community-1234/tutorial`` or
``http://127.0.0.1:8000/api/hooks/my-community-1234/tutorial/<webhook_slug>``, depending on whether the
``webhook_slug`` config option was set for the ``my-community-1234`` community.

Incoming POST requests to this endpoint will be routed to the ``receive_webhook`` function that we just defined.

You can test out your listener by using `ngrok <https://ngrok.com/>`_ to create a temporary public URL for your local development server.
Then, go to the external platform (Discourse, Open Collective, etc) and register your temporary URL. It will look something like:
``https://abc123.ngrok.io/api/hooks/my-community-1234/tutorial``

Now when you perform actions on the external platform, you should see events logged locally from your ``receive_webhook`` function.

.. note:: Get a list of all the webhook receiver endpoints for your community

    .. code-block:: shell

        curl 'http://127.0.0.1:8000/api/internal/community/my-community-1234/hooks'


Validating webhook requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Anyone on the internet can post requests to the metagov webhook receiver endpoints, so it's important to always verify the incoming requests to the extent possible. Some suggestions:

1. Ideally, the request can be verified using an event signature. This is not supported by all platforms. See the Discourse plugin for an example.
2. Use a hard-to-guess URL. The community slug should already be hard-to-guess, but we can make it even more difficult by setting the ``webhook_slug`` config property to a random string. The URL ends up looking like ``/api/hooks/<community_slug>/<plugin_name>/<webhook_slug>`` which is pretty hard to guess, so you can be reasonably sure that it's coming from the right place.
3. Don't rely on data in the webhook body. Always get data from the platform API instead of relying on what is in the webhook body. That way, even if the request is spoofed, we can find out from the platform API. See OpenCollective plugin for an example.


Governance Processes
********************

Create a proxy subclass of the ``GovernanceProcess`` Django model for our new governance process, ``MyGovProcess``.
This model should be declared after the ``Tutorial`` model.

Decorate it with the ``@Registry.governance_process`` decorator so that Metagov core picks it up.

In this example, the process will be exposed as an endpoint at ``/process/tutorial.my-gov-process``.

See the :ref:`Autodocumentation <autodocs-ref>` and complete example plugin for more information on how to implement each function.

.. code-block:: python

    @Registry.governance_process
    class MyGovProcess(GovernanceProcess):
        name = 'my-gov-process'
        plugin_name = 'tutorial'
        input_schema = {} #optional jsonschema for validation

        class Meta:
            proxy = True

        def start(self, parameters):
            # kick off the asynchronous governance process and return immediately
            pass

        def close(self):
            # close the governance process; save the outcome
            pass

        def check_status(self):
            # poll the governance process; update state if necessary
            pass

        def receive_webhook(self, request):
            # receive incoming webhook; update state if necessary
            pass
